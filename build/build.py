from typing import TYPE_CHECKING

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from src.llm import LLMRepositoryFactory
from src.llm import LLMConnection
from src.llm import Model2VecRepository

from src.router import RouterRepository

from src.app.adapters import RouterAdapter
from src.app.intelligence import RoutingIntelligenceLayer
from src.app.factory import ApplicationRepositoryFactory
from src.app.adapters import ChatAdapter, ModelsAdapter, MetricsAdapter, AdminAdapter
from src.app.migrations import BaseMigration
from src.app.injector import container
from src.app.exceptions.handlers import (ErrorSpec, status_handler, validation_error_handler, http_error_handler,
                                         unexpected_error_handler)
from src.app.exceptions import (ModelSemanticNotFound, PermissionDeniedForModel,
                                APIKeyInvalidOrExpired, CreditExhaustion, RateLimitedFromModelProvider,
                                ModelProviderServerError, APIError, BadRequestToModel, InvalidAdminCredentials,
                                NoHealthyModelAvailable)

from src.cache import (RedisRepository, QdrantRepository, RedisRankingRepository, RedisMetricsRepository, RedisRateLimiter,
                       ResponseCache)
from src.cache.keys import CacheKeyBuilder

from src.jobs import JobQueueConnection
from src.jobs import RedisStreamRepository, MetricsAggregator
from src.jobs.log_shipper import LogShipper, tune_logging_for_speed
from src.jobs.helpers import AddToCacheHelper, AnalyticsHelper, LoggingHelper

from src.utils.config import Config
from src.utils.types import ApplicationRepositoryType, RedisStreamName

from src.cache import CacheConnection

from .installation import MiddlewareInstallation, APIRouterInstallation

if TYPE_CHECKING:
    from fastapi import FastAPI

class Builder:
    def __init__(self, app: FastAPI):
        self.app: FastAPI = app
        self.config = Config()
        self._EXCEPTION_STATUS_CODES: dict[type[Exception], ErrorSpec] = {
            ModelSemanticNotFound: ErrorSpec(404, "invalid_request_error", "model_not_found"),
            BadRequestToModel: ErrorSpec(400, "invalid_request_error"),
            RateLimitedFromModelProvider: ErrorSpec(429, "rate_limit_error", "upstream_rate_limited"),
            APIKeyInvalidOrExpired: ErrorSpec(502, "api_error", "upstream_auth_failed"),
            PermissionDeniedForModel: ErrorSpec(502, "api_error", "upstream_permission_denied"),
            CreditExhaustion: ErrorSpec(502, "api_error", "upstream_credit_exhausted"),
            ModelProviderServerError: ErrorSpec(502, "api_error", "upstream_server_error"),
            APIError: ErrorSpec(502, "api_error", "upstream_connection_error"),
            InvalidAdminCredentials: ErrorSpec(401, "invalid_request_error", "invalid_credentials"),
            NoHealthyModelAvailable: ErrorSpec(503, "server_error", "no_model_available"),
        }

    @property
    def exception_map(self):
        return self._EXCEPTION_STATUS_CODES

    def build_and_initialize_app(self):
        self.__create_and_initialize_connections()
        self.__register_dependencies()

        self.__install_middleware()
        self.__install_routers()

        self.__register_exception_handlers()
        self.__setup_job_manager()

    def __install_middleware(self):
        MiddlewareInstallation.install_middleware(self.app)

    def __install_routers(self):
        APIRouterInstallation.install_api_routers(self.app)

    @staticmethod
    def __register_dependencies():
        container.register(Config, lambda : Config())
        container.register(Model2VecRepository, lambda: Model2VecRepository())
        container.register(QdrantRepository, lambda: QdrantRepository())
        container.register(RedisRankingRepository, lambda: RedisRankingRepository())
        container.register(RedisRepository, lambda: RedisRepository())
        container.register(RedisMetricsRepository, lambda: RedisMetricsRepository())
        container.register(BaseMigration, lambda: BaseMigration())
        container.register(RedisStreamRepository, lambda: RedisStreamRepository())

        container.register(ApplicationRepositoryFactory, lambda: ApplicationRepositoryFactory(
                                                                        container.resolve(Model2VecRepository),
                                                                        container.resolve(RedisRepository),
                                                                        container.resolve(QdrantRepository),
                                                                        container.resolve(RedisRankingRepository)))
        container.register(LLMRepositoryFactory, lambda: LLMRepositoryFactory(
                                                                        container.resolve(Config)))

        container.register(RedisRateLimiter, lambda: RedisRateLimiter(container.resolve(Config)))

        container.register(RouterRepository, lambda: RouterRepository(container.resolve(LLMRepositoryFactory),
                                                                        container.resolve(RouterAdapter),
                                                                        container.resolve(Config)))

        container.register(CacheKeyBuilder, lambda: CacheKeyBuilder())

        container.register(ResponseCache, lambda: ResponseCache(
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.EXACT_CACHE),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.EMBEDDING),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.VECTOR_CACHE),
                                                                        container.resolve(RedisStreamRepository),
                                                                        container.resolve(CacheKeyBuilder)))

        container.register(ChatAdapter, lambda: ChatAdapter(container.resolve(ResponseCache),
                                                                        container.resolve(RouterRepository)))

        container.register(ModelsAdapter, lambda: ModelsAdapter(container.resolve(RouterRepository)))

        container.register(MetricsAggregator, lambda: MetricsAggregator(
                                                                        container.resolve(RedisMetricsRepository),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.RANKING),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.VECTOR_CACHE),
                                                                        container.resolve(RouterRepository),
                                                                        container.resolve(RoutingIntelligenceLayer)))

        container.register(MetricsAdapter, lambda: MetricsAdapter(container.resolve(MetricsAggregator)))

        container.register(AdminAdapter, lambda: AdminAdapter(container.resolve(Config),
                                                                        container.resolve(RedisRepository)))


        container.register(RoutingIntelligenceLayer, lambda: RoutingIntelligenceLayer(
                                                                        container.resolve(ApplicationRepositoryFactory)))

        container.register(RouterAdapter, lambda: RouterAdapter(
                                                                        container.resolve(RedisStreamRepository),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.RANKING),
                                                                        container.resolve(RoutingIntelligenceLayer),
                                                                        container.resolve(LLMRepositoryFactory)))

        container.register(LoggingHelper, lambda: LoggingHelper())

        container.register(AnalyticsHelper, lambda: AnalyticsHelper(
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.RANKING),
                                                                        container.resolve(RedisMetricsRepository)))

        container.register(AddToCacheHelper, lambda: AddToCacheHelper(
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.EXACT_CACHE),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.EMBEDDING),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.VECTOR_CACHE)))

    @staticmethod
    def __setup_job_manager():
        scheduler = container.resolve(RedisStreamRepository)

        add_to_cache = container.resolve(AddToCacheHelper)
        scheduler.register_helper(RedisStreamName.RESPONSE_CACHE, add_to_cache)

        analytics_helper = container.resolve(AnalyticsHelper)
        scheduler.register_helper(RedisStreamName.ANALYTICS, analytics_helper)

        logging_helper = container.resolve(LoggingHelper)
        scheduler.register_helper(RedisStreamName.LOGGING, logging_helper)

    def __register_exception_handlers(self):
        for exception_class, error_spec in self._EXCEPTION_STATUS_CODES.items():
            self.app.add_exception_handler(exception_class, status_handler(error_spec))
        self.app.add_exception_handler(RequestValidationError, validation_error_handler) #type: ignore
        self.app.add_exception_handler(HTTPException, http_error_handler) #type: ignore
        self.app.add_exception_handler(Exception, unexpected_error_handler)

    def __create_and_initialize_connections(self):
        CacheConnection.initialize(self.config)
        LLMConnection.initialize(self.config)
        JobQueueConnection.initialize()
        self.__start_log_shipping()

    def __start_log_shipping(self):
        # started first, so anything logged while the rest of the app is built is shipped too
        tune_logging_for_speed()
        log_shipper = LogShipper(CacheConnection.create_sync_redis(self.config))
        log_shipper.install()
        container.register(LogShipper, lambda: log_shipper)

"""
의존성 주입 컨테이너
Dependency Inversion Principle 적용을 위한 DI 구조
"""

import logging
from typing import Dict, Any, Optional, Protocol, TypeVar, Type, Callable
from dataclasses import dataclass
from pathlib import Path
import inspect

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceProvider(Protocol):
    """서비스 제공자 프로토콜"""

    def get_service(self, service_type: Type[T]) -> T:
        """서비스 인스턴스 반환"""
        ...

    def register_service(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """서비스 팩토리 등록"""
        ...


@dataclass
class ServiceRegistration:
    """서비스 등록 정보"""

    service_type: Type
    factory: Callable[[], Any]
    singleton: bool = True
    instance: Optional[Any] = None


class DIContainer:
    """의존성 주입 컨테이너"""

    def __init__(self):
        self._services: Dict[Type, ServiceRegistration] = {}
        self._resolving: set = set()  # 순환 의존성 방지

    def register(
        self, service_type: Type[T], factory: Callable[[], T], singleton: bool = True
    ) -> None:
        """서비스 등록"""
        self._services[service_type] = ServiceRegistration(
            service_type=service_type, factory=factory, singleton=singleton
        )
        logger.debug(f"Registered service: {service_type.__name__}")

    def register_instance(self, service_type: Type[T], instance: T) -> None:
        """인스턴스 직접 등록"""
        self._services[service_type] = ServiceRegistration(
            service_type=service_type,
            factory=lambda: instance,
            singleton=True,
            instance=instance,
        )
        logger.debug(f"Registered instance: {service_type.__name__}")

    def resolve(self, service_type: Type[T]) -> T:
        """서비스 인스턴스 해결"""
        if service_type in self._resolving:
            raise ValueError(
                f"Circular dependency detected for {service_type.__name__}"
            )

        if service_type not in self._services:
            # 자동 등록 시도 (생성자 주입)
            if self._can_auto_register(service_type):
                self._auto_register(service_type)
            else:
                raise ValueError(f"Service not registered: {service_type.__name__}")

        registration = self._services[service_type]

        # 싱글톤이고 이미 인스턴스가 있으면 반환
        if registration.singleton and registration.instance is not None:
            return registration.instance

        try:
            self._resolving.add(service_type)
            instance = registration.factory()

            if registration.singleton:
                registration.instance = instance

            logger.debug(f"Resolved service: {service_type.__name__}")
            return instance

        finally:
            self._resolving.discard(service_type)

    def _can_auto_register(self, service_type: Type) -> bool:
        """자동 등록 가능 여부 확인"""
        try:
            # 구체 클래스인지 확인
            if inspect.isabstract(service_type):
                return False

            # 생성자가 있는지 확인
            if not hasattr(service_type, "__init__"):
                return False

            return True
        except Exception:
            return False

    def _auto_register(self, service_type: Type) -> None:
        """자동 서비스 등록"""

        def factory():
            # 생성자 파라미터 분석
            signature = inspect.signature(service_type.__init__)
            kwargs = {}

            for param_name, param in signature.parameters.items():
                if param_name == "self":
                    continue

                # 타입 힌트가 있으면 해당 서비스 해결
                if param.annotation != inspect.Parameter.empty:
                    kwargs[param_name] = self.resolve(param.annotation)
                elif param.default != inspect.Parameter.empty:
                    # 기본값 사용
                    kwargs[param_name] = param.default
                else:
                    # Optional 파라미터는 None으로
                    kwargs[param_name] = None

            return service_type(**kwargs)

        self.register(service_type, factory)

    def is_registered(self, service_type: Type) -> bool:
        """서비스 등록 여부 확인"""
        return service_type in self._services

    def clear(self) -> None:
        """모든 서비스 등록 해제"""
        self._services.clear()
        self._resolving.clear()
        logger.debug("Cleared all service registrations")


class ServiceLocator:
    """서비스 로케이터 패턴"""

    _instance: Optional["ServiceLocator"] = None
    _container: Optional[DIContainer] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._container = DIContainer()
        return cls._instance

    @classmethod
    def get_service(cls, service_type: Type[T]) -> T:
        """서비스 인스턴스 가져오기"""
        instance = cls()
        return instance._container.resolve(service_type)

    @classmethod
    def register_service(
        cls, service_type: Type[T], factory: Callable[[], T], singleton: bool = True
    ) -> None:
        """서비스 등록"""
        instance = cls()
        instance._container.register(service_type, factory, singleton)

    @classmethod
    def register_instance(cls, service_type: Type[T], instance: T) -> None:
        """인스턴스 등록"""
        locator = cls()
        locator._container.register_instance(service_type, instance)

    @classmethod
    def is_registered(cls, service_type: Type) -> bool:
        """등록 여부 확인"""
        instance = cls()
        return instance._container.is_registered(service_type)

    @classmethod
    def clear(cls) -> None:
        """모든 등록 해제"""
        if cls._instance and cls._container:
            cls._container.clear()


# 의존성 주입 데코레이터
def injectable(cls):
    """의존성 주입 가능 클래스 마커"""
    cls._injectable = True
    return cls


def inject(dependency_type: Type[T]) -> T:
    """의존성 주입 함수"""
    return ServiceLocator.get_service(dependency_type)


# 컨텍스트 매니저를 통한 스코프 관리
class DIScope:
    """의존성 주입 스코프"""

    def __init__(self, container: DIContainer):
        self.container = container
        self.temp_registrations: Dict[Type, ServiceRegistration] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 임시 등록들 정리
        for service_type in self.temp_registrations:
            if service_type in self.container._services:
                del self.container._services[service_type]

    def register_scoped(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """스코프 내에서만 유효한 서비스 등록"""
        self.container.register(service_type, factory, singleton=False)
        self.temp_registrations[service_type] = self.container._services[service_type]


# 설정 기반 DI 컨테이너
class ConfigurableDIContainer(DIContainer):
    """설정 파일 기반 DI 컨테이너"""

    def __init__(self, config_path: Optional[Path] = None):
        super().__init__()
        self.config_path = config_path
        if config_path and config_path.exists():
            self._load_configuration()

    def _load_configuration(self) -> None:
        """설정 파일에서 서비스 등록 정보 로드"""
        try:
            import yaml

            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            services_config = config.get("services", {})

            for service_name, service_config in services_config.items():
                self._register_from_config(service_name, service_config)

        except Exception as e:
            logger.error(f"Failed to load DI configuration: {e}")

    def _register_from_config(self, service_name: str, config: Dict[str, Any]) -> None:
        """설정에서 서비스 등록"""
        try:
            # 모듈과 클래스 이름으로 타입 해결
            module_name = config.get("module")
            class_name = config.get("class")

            if not module_name or not class_name:
                logger.warning(f"Invalid service configuration for {service_name}")
                return

            # 동적 임포트
            module = __import__(module_name, fromlist=[class_name])
            service_type = getattr(module, class_name)

            # 팩토리 함수 생성
            def factory():
                constructor_args = config.get("constructor_args", {})
                resolved_args = {}

                for arg_name, arg_config in constructor_args.items():
                    if isinstance(arg_config, dict) and "service_type" in arg_config:
                        # 다른 서비스 참조
                        dep_module = __import__(
                            arg_config["module"], fromlist=[arg_config["service_type"]]
                        )
                        dep_type = getattr(dep_module, arg_config["service_type"])
                        resolved_args[arg_name] = self.resolve(dep_type)
                    else:
                        # 일반 값
                        resolved_args[arg_name] = arg_config

                return service_type(**resolved_args)

            singleton = config.get("singleton", True)
            self.register(service_type, factory, singleton)

            logger.info(f"Registered service from config: {service_name}")

        except Exception as e:
            logger.error(f"Failed to register service {service_name}: {e}")


# 글로벌 DI 컨테이너 인스턴스
_global_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """글로벌 DI 컨테이너 가져오기"""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def set_container(container: DIContainer) -> None:
    """글로벌 DI 컨테이너 설정"""
    global _global_container
    _global_container = container


# 유틸리티 함수들
def resolve_service(service_type: Type[T]) -> T:
    """글로벌 컨테이너에서 서비스 해결"""
    return get_container().resolve(service_type)


def register_service(
    service_type: Type[T], factory: Callable[[], T], singleton: bool = True
) -> None:
    """글로벌 컨테이너에 서비스 등록"""
    get_container().register(service_type, factory, singleton)


def register_instance(service_type: Type[T], instance: T) -> None:
    """글로벌 컨테이너에 인스턴스 등록"""
    get_container().register_instance(service_type, instance)

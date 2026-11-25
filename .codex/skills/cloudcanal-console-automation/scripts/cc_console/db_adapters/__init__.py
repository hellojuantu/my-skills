from cc_console.datasource import normalize_ds_type

from .base import AdapterCapabilityError
from .api_ai import LlmFamilyAdapter, RagApiFamilyAdapter
from .cache import LindormFamilyAdapter, RedisFamilyAdapter
from .document import DynamoDbFamilyAdapter, MongoFamilyAdapter
from .lakehouse import FileFamilyAdapter, HostedFileFamilyAdapter, LakehouseFamilyAdapter, SnowflakeFamilyAdapter, SpannerFamilyAdapter, TunnelFamilyAdapter
from .mq import KafkaFamilyAdapter, PulsarFamilyAdapter, RabbitMqFamilyAdapter, RocketMqFamilyAdapter
from .mysql_family import MySqlFamilyAdapter, DEFAULT_PROFILE as MYSQL_DEFAULT_PROFILE
from .rdb import (
    ClickHouseFamilyAdapter,
    DamengFamilyAdapter,
    Db2FamilyAdapter,
    DuckDbFamilyAdapter,
    HanaFamilyAdapter,
    OracleFamilyAdapter,
    PostgresFamilyAdapter,
    SqlServerFamilyAdapter,
    TimeSeriesFamilyAdapter,
)
from .search import ElasticSearchFamilyAdapter


ADAPTERS = [
    MySqlFamilyAdapter(),
    PostgresFamilyAdapter(),
    OracleFamilyAdapter(),
    SqlServerFamilyAdapter(),
    Db2FamilyAdapter(),
    HanaFamilyAdapter(),
    DamengFamilyAdapter(),
    ClickHouseFamilyAdapter(),
    DuckDbFamilyAdapter(),
    TimeSeriesFamilyAdapter(),
    KafkaFamilyAdapter(),
    RocketMqFamilyAdapter(),
    RabbitMqFamilyAdapter(),
    PulsarFamilyAdapter(),
    RedisFamilyAdapter(),
    LindormFamilyAdapter(),
    ElasticSearchFamilyAdapter(),
    MongoFamilyAdapter(),
    DynamoDbFamilyAdapter(),
    FileFamilyAdapter(),
    HostedFileFamilyAdapter(),
    LakehouseFamilyAdapter(),
    TunnelFamilyAdapter(),
    SnowflakeFamilyAdapter(),
    SpannerFamilyAdapter(),
    RagApiFamilyAdapter(),
    LlmFamilyAdapter(),
]


def adapter_reports():
    return [adapter.dependency_report() for adapter in ADAPTERS]


def adapter_by_name(name):
    for adapter in ADAPTERS:
        if adapter.name == name:
            return adapter
    raise AdapterCapabilityError("unknown adapter: " + str(name))


def install_dependency_commands(adapter_name=None):
    adapters = ADAPTERS if adapter_name in (None, "", "all") else [adapter_by_name(adapter_name)]
    commands = []
    for adapter in adapters:
        for command in adapter.install_commands:
            if command not in commands:
                commands.append(command)
    return commands


def adapter_for_type(ds_type):
    normalized = normalize_ds_type(ds_type)
    for adapter in ADAPTERS:
        if adapter.supports_type(normalized):
            return adapter
    raise AdapterCapabilityError("no database adapter registered for datasource type " + normalized)


def adapter_for_pair(source_type, target_type):
    source_adapter = adapter_for_type(source_type)
    target_adapter = adapter_for_type(target_type)
    return source_adapter, target_adapter


def profile_tables(ds_type, profile=None):
    adapter = adapter_for_type(ds_type)
    return adapter.profile_tables(profile or adapter.default_profile)

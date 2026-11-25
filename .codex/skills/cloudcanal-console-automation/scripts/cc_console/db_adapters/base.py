import importlib.util

from cc_console.client import ApiError


TEMP_SCHEMA_PREFIX = "cc_auto_"


class AdapterCapabilityError(ApiError):
    pass


def dependency_status(modules):
    result = {}
    for module in modules:
        try:
            result[module] = bool(importlib.util.find_spec(module))
        except ModuleNotFoundError:
            result[module] = False
    return result


def require_modules(modules, install_commands):
    missing = [module for module, ok in dependency_status(modules).items() if not ok]
    if missing:
        raise AdapterCapabilityError(
            "missing database driver modules: "
            + ",".join(missing)
            + ". Install with: "
            + " && ".join(install_commands)
        )


def parse_host_port(host_value, default_port):
    if not host_value:
        raise ValueError("datasource host is empty")
    host = str(host_value).strip()
    if host.startswith("[") and "]" in host:
        end = host.index("]")
        name = host[1:end]
        rest = host[end + 1 :]
        if rest.startswith(":"):
            return name, int(rest[1:])
        return name, default_port
    if ":" in host:
        name, port = host.rsplit(":", 1)
        if port:
            return name, int(port)
    return host, default_port


def require_temp_schema(schema, allow_non_temp=False):
    if allow_non_temp:
        return
    if not schema or not schema.startswith(TEMP_SCHEMA_PREFIX):
        raise ValueError(
            "refusing to mutate non-temp schema "
            + str(schema)
            + "; use --allow-non-temp-schema to override"
        )


def safe_object_name(*parts, max_length=63):
    text = "_".join(str(part or "") for part in parts if part not in (None, ""))
    cleaned = []
    previous_underscore = False
    for ch in text.lower():
        ok = ch.isalnum() or ch in ("_", "-")
        value = ch if ok else "_"
        if value == "_":
            if not previous_underscore:
                cleaned.append(value)
            previous_underscore = True
        else:
            cleaned.append(value)
            previous_underscore = False
    result = "".join(cleaned).strip("_-")
    if not result:
        result = "cc_auto_obj"
    if len(result) > max_length:
        result = result[:max_length].rstrip("_-")
    return result


class DatabaseAdapter:
    name = "base"
    data_source_types = ()
    source_data_types = ()
    target_data_types = ()
    driver_modules = ()
    install_commands = ()
    default_profile = None
    data_model = "generic"
    can_init_source = False
    can_prepare_target = False
    can_cleanup = False
    can_faker_crud = False
    can_compare = False

    def dependency_report(self):
        return {
            "adapter": self.name,
            "dataSourceTypes": list(self.data_source_types),
            "dataModel": self.data_model,
            "defaultProfile": self.default_profile,
            "capabilities": self.capabilities(),
            "driverModules": dependency_status(self.driver_modules),
            "installCommands": list(self.install_commands),
        }

    def capabilities(self):
        return {
            "profileTables": True,
            "initSource": bool(self.can_init_source),
            "prepareTarget": bool(self.can_prepare_target),
            "cleanup": bool(self.can_cleanup),
            "fakerCrud": bool(self.can_faker_crud),
            "compare": bool(self.can_compare),
        }

    def require_dependencies(self):
        require_modules(self.driver_modules, self.install_commands)

    def supports_type(self, ds_type):
        return ds_type in self.data_source_types

    def supports_source(self, ds_type):
        return ds_type in self.source_data_types

    def supports_target(self, ds_type):
        return ds_type in self.target_data_types

    def profile_tables(self, profile):
        prefix = "cc_auto_" + self.name.replace("-family", "").replace("-", "_")
        return [
            prefix + "_obj_01",
            prefix + "_obj_02",
            prefix + "_obj_03",
            prefix + "_obj_04",
            prefix + "_obj_05",
        ]

    def profile_tables_for_namespace(self, profile, namespace):
        return self.profile_tables(profile)

    def init_source_dataset(self, ds, password, schema, rows, profile, drop_existing, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement source dataset initialization")

    def prepare_target_dataset(self, ds, password, schema, drop_existing, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement target dataset preparation")

    def cleanup_dataset(self, ds, password, schema, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement dataset cleanup")

    def faker_crud(self, ds, password, schema, rounds, profile, seed, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement faker CRUD")

    def compare_datasets(self, source_ds, target_ds, source_password, target_password, source_schema, target_schema, profile, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement dataset comparison")

    def table_snapshot(self, ds, password, schema, table, check_mode, allow_non_temp, **kwargs):
        raise AdapterCapabilityError(self.name + " does not implement table snapshot")

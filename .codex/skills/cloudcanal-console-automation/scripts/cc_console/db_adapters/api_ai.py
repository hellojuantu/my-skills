from .base import DatabaseAdapter


class RoutedApiFamilyAdapter(DatabaseAdapter):
    can_init_source = False
    can_prepare_target = False
    can_cleanup = False
    can_faker_crud = False
    can_compare = False

    def capabilities(self):
        result = super().capabilities()
        result["profileTables"] = False
        return result

    def profile_tables(self, profile):
        if profile != self.default_profile:
            raise ValueError("unsupported " + self.name + " profile: " + str(profile))
        return []

    def profile_tables_for_namespace(self, profile, namespace):
        return self.profile_tables(profile)


class RagApiFamilyAdapter(RoutedApiFamilyAdapter):
    name = "rag-api-family"
    data_source_types = ("RagApi",)
    source_data_types = ()
    target_data_types = data_source_types
    default_profile = "rag-api-routed"
    data_model = "api-rag-routed"


class LlmFamilyAdapter(RoutedApiFamilyAdapter):
    name = "llm-family"
    data_source_types = ("OpenAI", "DashScope", "HuggingFace", "Cohere", "DeepSeek", "LocalAI", "Ollama", "ZhipuAI", "Anthropic", "Bedrock")
    source_data_types = ()
    target_data_types = ()
    default_profile = "llm-routed"
    data_model = "api-llm-routed"

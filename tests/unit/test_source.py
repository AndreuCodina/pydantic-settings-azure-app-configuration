from azure.appconfiguration import (
    ConfigurationSetting,
    SecretReferenceConfigurationSetting,
)
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import KeyVaultSecret, SecretProperties
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pytest_mock import MockerFixture

from pydantic_settings_azure_app_configuration.source import (
    AzureAppConfigurationSettingsSource,
)

_PREFIX = "my_api__"


class _SqlServer(BaseModel):
    password: str
    host: str


class _AzureKeyVaultSettings(BaseSettings):
    logging_level: str
    sql_server: _SqlServer

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        azure_credential = DefaultAzureCredential()
        azure_app_configuration = AzureAppConfigurationSettingsSource(
            settings_cls,
            lambda app_configuration_options: app_configuration_options.connect_with_url(
                "https://test.azconfig.io", azure_credential
            )
            .select_key(f"{_PREFIX}*")
            .trim_key_prefix(f"{_PREFIX}")
            .configure_key_vault(
                lambda key_vault_options: key_vault_options.set_credential(
                    azure_credential
                )
            ),
            env_nested_delimiter="__",
        )
        return (azure_app_configuration,)


class TestSource:
    def test_get_configurations(self, mocker: MockerFixture) -> None:
        expected_value = "Value"
        configurations = [
            ConfigurationSetting(key=f"{_PREFIX}logging_level", value=expected_value),
            SecretReferenceConfigurationSetting(
                key=f"{_PREFIX}sql_server__password",
                secret_id="https://test.vault.azure.net/secrets/password",
            ),
            ConfigurationSetting(
                key=f"{_PREFIX}sql_server__host", value=expected_value
            ),
        ]
        mocker.patch(
            "azure.appconfiguration.AzureAppConfigurationClient.list_configuration_settings",
            return_value=configurations,
        )
        key_vault_value = KeyVaultSecret(SecretProperties(), expected_value)
        mocker.patch(
            "azure.keyvault.secrets.SecretClient.get_secret",
            return_value=key_vault_value,
        )

        _AzureKeyVaultSettings()  # type: ignore

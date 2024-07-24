from typing import Callable, Mapping, Optional, Self

from azure.appconfiguration import (
    AzureAppConfigurationClient,
    ConfigurationSetting,
    FeatureFlagConfigurationSetting,
    SecretReferenceConfigurationSetting,
)
from azure.core.credentials import TokenCredential
from azure.keyvault.secrets import SecretClient
from pydantic import BaseModel
from pydantic_settings import BaseSettings, EnvSettingsSource
from pydantic_settings.sources import SettingsError


class _AzureAppConfigurationKeySelector(BaseModel):
    key_filter: str
    label_filter: Optional[str] = None


class AzureAppConfigurationKeyFilter:
    ANY: str = "*"


class AzureAppConfigurationKeyVaultOptions:
    credential: Optional[TokenCredential]

    def set_credential(self, credential: TokenCredential) -> Self:
        self.credential = credential
        return self


class AzureAppConfigurationOptions:
    url: Optional[str]
    credential: Optional[TokenCredential]
    connection_string: Optional[str]
    key_selectors: list[_AzureAppConfigurationKeySelector]
    prefixes_to_trim: list[str]
    key_vault_options: Optional[AzureAppConfigurationKeyVaultOptions]

    def __init__(self) -> None:
        self.url = None
        self.credential = None
        self.connection_string = None
        self.key_selectors = []
        self.prefixes_to_trim = []
        self.key_vault_options = None

    def connect_with_url(self, url: str, credential: TokenCredential) -> Self:
        self.url = url
        self.credential = credential
        return self

    def connect_with_connection_string(self, connection_string: str) -> Self:
        self.connection_string = connection_string
        return self

    def select_key(self, key_filter: str, label_filter: Optional[str] = None) -> Self:
        self.key_selectors.append(
            _AzureAppConfigurationKeySelector(
                key_filter=key_filter, label_filter=label_filter
            )
        )
        return self

    def trim_key_prefix(self, prefix: str) -> Self:
        self.prefixes_to_trim.append(prefix)
        return self

    def configure_key_vault(
        self,
        configure: Callable[
            [AzureAppConfigurationKeyVaultOptions], AzureAppConfigurationKeyVaultOptions
        ],
    ) -> Self:
        self.key_vault_options = AzureAppConfigurationKeyVaultOptions()
        configure(self.key_vault_options)
        return self


class AzureAppConfigurationSettingsSource(EnvSettingsSource):
    _configure: Callable[[AzureAppConfigurationOptions], AzureAppConfigurationOptions]
    _options: Optional[AzureAppConfigurationOptions]

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        configure: Callable[
            [AzureAppConfigurationOptions], AzureAppConfigurationOptions
        ],
        env_nested_delimiter: Optional[str] = None,
        env_parse_none_str: Optional[str] = None,
        env_parse_enums: Optional[bool] = None,
    ) -> None:
        self._configure = configure
        self._options = None
        super().__init__(
            settings_cls,
            case_sensitive=True,
            env_prefix="",
            env_nested_delimiter=env_nested_delimiter,
            env_ignore_empty=False,
            env_parse_none_str=env_parse_none_str,
            env_parse_enums=env_parse_enums,
        )

    def __repr__(self) -> str:
        return f"{AzureAppConfigurationSettingsSource.__name__}(env_nested_delimiter={self.env_nested_delimiter})"

    def _load_env_vars(self) -> Mapping[str, Optional[str]]:
        self._options = AzureAppConfigurationOptions()
        self._configure(self._options)
        app_configuration_client = self._get_configuration_client()
        default_key_selector = _AzureAppConfigurationKeySelector(
            key_filter=AzureAppConfigurationKeyFilter.ANY
        )
        key_selectors = (
            self._options.key_selectors
            if len(self._options.key_selectors) > 0
            else [default_key_selector]
        )
        env_vars: dict[str, Optional[str]] = {}

        for key_selector in key_selectors:
            settings = app_configuration_client.list_configuration_settings(
                key_filter=key_selector.key_filter,
                label_filter=key_selector.label_filter,
            )

            for setting in settings:
                setting_key = self._get_setting_key(setting)
                setting_value = self._get_setting_value(setting)
                env_vars[setting_key] = setting_value

        return env_vars

    def _get_configuration_client(self) -> AzureAppConfigurationClient:
        assert self._options is not None

        if self._options.url is not None and self._options.credential is not None:
            return AzureAppConfigurationClient(
                base_url=self._options.url, credential=self._options.credential
            )
        elif self._options.connection_string is not None:
            return AzureAppConfigurationClient.from_connection_string(
                self._options.connection_string
            )

        raise SettingsError(
            f"Use {AzureAppConfigurationOptions.connect_with_url.__name__} or {AzureAppConfigurationOptions.connect_with_connection_string.__name__} to specify how to connect to Azure App Configuration"
        )

    def _get_setting_key(self, setting: ConfigurationSetting) -> str:
        key = setting.key
        assert self._options is not None

        for prefix in self._options.prefixes_to_trim:
            if setting.key.startswith(prefix):
                return key[len(prefix) :]

        return key

    def _get_setting_value(self, setting: ConfigurationSetting) -> str:
        match setting:
            case SecretReferenceConfigurationSetting():
                secret_id = setting.secret_id
                assert secret_id is not None
                return self._get_key_vault_secret_value(secret_id)
            case FeatureFlagConfigurationSetting():
                raise SettingsError("Feature flags are not supported")
            case ConfigurationSetting():
                return setting.value

    def _get_key_vault_secret_value(self, secret_id: str) -> str:
        assert self._options is not None
        assert self._options.key_vault_options is not None
        assert self._options.key_vault_options.credential is not None
        key_vault_url, secret_name = secret_id.split("/secrets/")
        secret_client = SecretClient(
            vault_url=key_vault_url,
            credential=self._options.key_vault_options.credential,
        )
        secret = secret_client.get_secret(secret_name)
        assert secret.value is not None
        return secret.value

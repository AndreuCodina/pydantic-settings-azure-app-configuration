# pydantic-settings-azure-app-configuration

[![pypi](https://img.shields.io/pypi/v/pydantic-settings-azure-app-configuration.svg)](https://pypi.python.org/pypi/pydantic-settings-azure-app-configuration)
[![license](https://img.shields.io/github/license/AndreuCodina/pydantic-settings-azure-app-configuration.svg)](https://github.com/AndreuCodina/pydantic-settings-azure-app-configuration/blob/main/LICENSE)
[![versions](https://img.shields.io/pypi/pyversions/pydantic-settings-azure-app-configuration.svg)](https://github.com/AndreuCodina/pydantic-settings-azure-app-configuration)

## Introduction

https://learn.microsoft.com/en-us/azure/azure-app-configuration/overview

## Installation

```bash
pip install pydantic-settings-azure-app-configuration
```

## Usage

By default, it loads all the values from Azure App Configuration, but you can assign a prefix to your application (e.g. `my_api__`) and load only the values for it using the `select_key` method. You can also use the `trim_key_prefix` method to remove the prefix from the value names.

Furthermore, if some value references a secret stored in Azure Key Vault, you can use the `configure_key_vault` method to retrieve it.

If you use Entra ID authentication, you can use the role `App Configuration Data Reader` to access the configurations and `Key Vault Secrets User` to access the secrets.

To nest models you have to define a `env_nested_delimiter` (e.g. `__`), either in the source constructor or in the `model_config` class.

The configuration of this settings source is almost idental to the the provided by ASP.NET Core, in case you want to read the official documentation to inform you about more complex uses, best practices, etc.

```python
import os

from azure.identity import DefaultAzureCredential
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from src.pydantic_settings_azure_app_configuration.source import (
    AzureAppConfigurationSettingsSource,
)


import os

from azure.identity import DefaultAzureCredential
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from src.pydantic_settings_azure_app_configuration.source import (
    AzureAppConfigurationSettingsSource,
)


class SqlServer(BaseModel):
    password: str
    host: str


class AzureKeyVaultSettings(BaseSettings):
    logging_level: str
    sql_server: SqlServer

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
                os.environ["AZURE_APP_CONFIGURATION_URL"], azure_credential
            )
            .select_key("my_api__*")
            .trim_key_prefix("my_api__")
            .configure_key_vault(
                lambda key_vault_options: key_vault_options.set_credential(
                    azure_credential
                )
            ),
            env_nested_delimiter="__",
        )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            azure_app_configuration,
        )
```
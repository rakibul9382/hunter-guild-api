from django.apps import AppConfig


class GuildConfig(AppConfig):
    name = 'guild'

    def ready(self):
        import guild.signals

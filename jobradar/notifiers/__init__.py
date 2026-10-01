from jobradar.notifiers.base import Notifier, NotifierError
from jobradar.notifiers.discord import DiscordNotifier
from jobradar.notifiers.email import EmailNotifier
from jobradar.notifiers.telegram import TelegramNotifier

NOTIFIERS: dict[str, type[Notifier]] = {
    n.name: n for n in (TelegramNotifier, EmailNotifier, DiscordNotifier)
}

__all__ = ["NOTIFIERS", "Notifier", "NotifierError"]

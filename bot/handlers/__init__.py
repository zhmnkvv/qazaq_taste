from aiogram import Router

from bot.handlers import ai_chat, booking, common, events, menu, start


def _detach(router: Router) -> None:
    """Allow building a dispatcher more than once per process (e.g. in tests).

    aiogram routers are module-level singletons that can only have one parent.
    """
    parent = router.parent_router
    if parent is not None:
        parent.sub_routers.remove(router)
        router._parent_router = None


def build_root_router() -> Router:
    root = Router(name="root")
    for router in (
        start.router,             # /start, /help, /language
        common.nav_router,        # main buttons + commands + /cancel from any state
        menu.router,
        booking.router,
        events.router,
        ai_chat.router,
        common.fallback_router,   # must be last: free text -> AI consultant
    ):
        _detach(router)
        root.include_router(router)
    return root

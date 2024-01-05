from functools import wraps

import sublime
import sublime_plugin


from typing import Callable, Dict, List, Tuple, TypedDict, TypeVar
FrozenSel = List[Tuple[int, int]]
T = TypeVar("T", bound=sublime_plugin.EventListener)


class ViewState(TypedDict):
    sel: FrozenSel
    viewport: Tuple[float, float]


Filename = str
Store = Dict[Filename, ViewState]


def ensure_window(
    handler: Callable[[T, sublime.View, sublime.Window], None]
) -> Callable[[T, sublime.View], None]:
    @wraps(handler)
    def wrapper(self: T, view: sublime.View) -> None:
        window = view.window()
        if not window:
            return
        handler(self, view, window)
    return wrapper


class ReopenFilesListener(sublime_plugin.EventListener):
    # If the window was closed, we receive `on_pre_close` for each
    # view but all are detached hence `ensure_window`.
    # This is actually good behavior as Sublime will reload
    # the project with all views ("hot_exit") anyway so there is
    # no need to persist it here too.
    @ensure_window
    def on_pre_close(self, view: sublime.View, window: sublime.Window) -> None:
        if view.is_scratch():
            return

        file_name = view.file_name()
        if not file_name:
            return

        state: ViewState = {
            "sel": freeze_sel(view),
            "viewport": view.viewport_position()
        }
        store = window.settings().get("rf_store", {})
        store[file_name] = state
        window.settings().set("rf_store", store)

    @ensure_window
    # Use `on_load_async` here and check if the viewport or cursor
    # has been moved already to not override a possible
    # `window.open_file()` with a `row:col` pair.
    def on_load_async(self, view: sublime.View, window: sublime.Window) -> None:
        if view.is_scratch():
            return

        if (
            view.viewport_position() != (0, 0)
            or freeze_sel(view) != [(0, 0)]
        ):
            return

        file_name = view.file_name()
        if not file_name:
            return

        store: Store = window.settings().get("rf_store", {})
        try:
            state = store[file_name]
        except KeyError:
            return

        view.sel().clear()
        view.sel().add_all(unfreeze_sel(state["sel"]))

        view.set_viewport_position(state["viewport"])


def freeze_sel(view: sublime.View) -> FrozenSel:
    return [(s.a, s.b) for s in view.sel()]


def unfreeze_sel(sel: FrozenSel) -> List[sublime.Region]:
    return [sublime.Region(a, b) for (a, b) in sel]

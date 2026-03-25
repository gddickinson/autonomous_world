"""Interactive LLM console for in-game natural language commands.

Toggle with backtick (`) key. Type commands that get processed by the LLM
or fall back to keyword matching when no LLM is available.

Command processing logic is in llm_commands.py.
"""

import pygame
from collections import deque
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE
from game.ui.llm_commands import process_command


# Maximum console history and output lines
MAX_HISTORY = 50
MAX_OUTPUT = 10


class LLMConsole:
    """In-game console for natural language commands."""

    def __init__(self):
        self.visible = False
        self.input_text = ""
        self.cursor_pos = 0
        self.history: deque = deque(maxlen=MAX_HISTORY)
        self.history_idx = -1  # -1 = current input
        self.output_lines: deque = deque(maxlen=MAX_OUTPUT)
        self.scroll_offset = 0
        self._saved_input = ""  # saved when browsing history
        self._pending_request_id = None
        self._blink_timer = 0.0
        self._current_command = None

        # Fonts (initialized lazily)
        self._font = None
        self._font_sm = None

    def _ensure_fonts(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14)
            self._font_sm = pygame.font.SysFont("monospace", 12)

    def toggle(self):
        """Toggle console visibility."""
        self.visible = not self.visible
        if self.visible:
            self.input_text = ""
            self.cursor_pos = 0
            self.history_idx = -1

    def handle_event(self, event) -> bool:
        """Handle a pygame event. Returns True if consumed."""
        if not self.visible:
            return False
        if event.type != pygame.KEYDOWN:
            return False

        key = event.key
        mods = event.mod

        # Close console
        if key == pygame.K_BACKQUOTE:
            self.toggle()
            return True
        if key == pygame.K_ESCAPE:
            self.toggle()
            return True

        # Submit command
        if key == pygame.K_RETURN:
            if self.input_text.strip():
                self._submit()
            return True

        # History navigation
        if key == pygame.K_UP:
            self._history_up()
            return True
        if key == pygame.K_DOWN:
            self._history_down()
            return True

        # Text editing
        if key == pygame.K_BACKSPACE:
            if self.cursor_pos > 0:
                self.input_text = (
                    self.input_text[:self.cursor_pos - 1]
                    + self.input_text[self.cursor_pos:]
                )
                self.cursor_pos -= 1
            return True
        if key == pygame.K_DELETE:
            if self.cursor_pos < len(self.input_text):
                self.input_text = (
                    self.input_text[:self.cursor_pos]
                    + self.input_text[self.cursor_pos + 1:]
                )
            return True
        if key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
            return True
        if key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self.input_text), self.cursor_pos + 1)
            return True
        if key == pygame.K_HOME:
            self.cursor_pos = 0
            return True
        if key == pygame.K_END:
            self.cursor_pos = len(self.input_text)
            return True

        # Paste
        if key == pygame.K_v and (mods & pygame.KMOD_CTRL
                                  or mods & pygame.KMOD_META):
            try:
                clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                if clip:
                    text = clip.decode("utf-8", errors="ignore").rstrip("\x00")
                    self.input_text = (
                        self.input_text[:self.cursor_pos]
                        + text
                        + self.input_text[self.cursor_pos:]
                    )
                    self.cursor_pos += len(text)
            except Exception:
                pass
            return True

        # Character input
        ch = getattr(event, "unicode", "")
        if ch and ch.isprintable() and ch != "`":
            self.input_text = (
                self.input_text[:self.cursor_pos]
                + ch
                + self.input_text[self.cursor_pos:]
            )
            self.cursor_pos += 1
            return True

        return True  # consume all keys while console is open

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _history_up(self):
        if not self.history:
            return
        if self.history_idx == -1:
            self._saved_input = self.input_text
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.input_text = self.history[self.history_idx]
            self.cursor_pos = len(self.input_text)

    def _history_down(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self.input_text = self.history[self.history_idx]
            self.cursor_pos = len(self.input_text)
        elif self.history_idx == 0:
            self.history_idx = -1
            self.input_text = self._saved_input
            self.cursor_pos = len(self.input_text)

    # ------------------------------------------------------------------
    # Command submission
    # ------------------------------------------------------------------

    def _submit(self):
        text = self.input_text.strip()
        if not text:
            return
        self.history.appendleft(text)
        self.history_idx = -1
        self.output_lines.append(("cmd", f"> {text}"))
        self.input_text = ""
        self.cursor_pos = 0
        self._current_command = text

    def update(self, game):
        """Poll for pending LLM results and process queued commands."""
        # Check for pending LLM response
        if self._pending_request_id:
            result = game.llm.get_result(self._pending_request_id)
            if result:
                self.output_lines.append(("response", result))
                self._pending_request_id = None

        # Process queued command
        cmd = self._current_command
        if cmd:
            self._current_command = None
            process_command(self, cmd, game)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen):
        """Draw the console overlay."""
        if not self.visible:
            return

        self._ensure_fonts()
        self._blink_timer += 0.016  # ~60fps

        # Console background
        console_h = 220
        console_y = SCREEN_HEIGHT - console_h
        bg = pygame.Surface((SCREEN_WIDTH, console_h), pygame.SRCALPHA)
        bg.fill((10, 12, 25, 220))
        screen.blit(bg, (0, console_y))

        # Border
        pygame.draw.line(
            screen, (60, 80, 120),
            (0, console_y), (SCREEN_WIDTH, console_y), 2
        )

        # Title
        title = self._font_sm.render(
            "LLM Console (` to close, Enter to send)", True, (120, 140, 180)
        )
        screen.blit(title, (10, console_y + 4))

        # Output area
        out_y = console_y + 22
        line_h = 16
        visible_lines = min(MAX_OUTPUT, (console_h - 50) // line_h)

        lines = list(self.output_lines)
        start = max(0, len(lines) - visible_lines)
        for i, (kind, text) in enumerate(lines[start:]):
            color = _line_color(kind)
            display = text[:100] + "..." if len(text) > 100 else text
            surf = self._font_sm.render(display, True, color)
            screen.blit(surf, (12, out_y + i * line_h))

        # Input area
        input_y = console_y + console_h - 28
        pygame.draw.rect(
            screen, (25, 30, 45),
            (8, input_y - 2, SCREEN_WIDTH - 16, 22)
        )
        pygame.draw.rect(
            screen, (60, 80, 120),
            (8, input_y - 2, SCREEN_WIDTH - 16, 22), 1
        )

        # Prompt
        prompt_surf = self._font.render("> ", True, (100, 200, 100))
        screen.blit(prompt_surf, (12, input_y))
        prompt_w = prompt_surf.get_width()

        # Input text
        text_surf = self._font.render(self.input_text, True, WHITE)
        screen.blit(text_surf, (12 + prompt_w, input_y))

        # Cursor
        if int(self._blink_timer * 2) % 2 == 0:
            before_cursor = self._font.render(
                self.input_text[:self.cursor_pos], True, WHITE
            )
            cx = 12 + prompt_w + before_cursor.get_width()
            pygame.draw.line(
                screen, (200, 220, 255),
                (cx, input_y), (cx, input_y + 14), 1
            )


def _line_color(kind: str):
    colors = {
        "cmd": (160, 180, 220),
        "response": (220, 220, 240),
        "success": (80, 220, 80),
        "error": (220, 80, 80),
        "info": (180, 200, 240),
    }
    return colors.get(kind, (200, 200, 200))

"""
Claude Chat UI - in-game chat panel for God Mode.

Draws a chat window, handles text input, and displays Claude's responses.
Also includes the API key configuration dialog.
"""

import pygame
from typing import List, Tuple, Optional
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE, YELLOW, GRAY, GREEN, RED, ORANGE


class ClaudeChatUI:
    """In-game chat interface with Claude AI assistant."""

    def __init__(self, assistant, god_console):
        self.assistant = assistant
        self.god_console = god_console
        self.visible = False
        self.input_text = ""
        self.messages: List[Tuple[str, str]] = []  # (role, text)
        self.pending_commands: List[str] = []  # commands waiting to be executed
        self.scroll_offset = 0
        self.pending = False
        self.cursor_blink = 0.0

        # Fonts (initialized lazily)
        self._fonts_ready = False
        self._font = None
        self._font_sm = None
        self._font_title = None

    def _ensure_fonts(self):
        if not self._fonts_ready:
            self._font = pygame.font.SysFont("monospace", 13)
            self._font_sm = pygame.font.SysFont("monospace", 11)
            self._font_title = pygame.font.SysFont("monospace", 14, bold=True)
            self._fonts_ready = True

    def toggle(self):
        self.visible = not self.visible

    def _wrap_text(self, text: str, max_width: int, font) -> List[str]:
        """Word-wrap text to fit within max_width pixels."""
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            words = paragraph.split()
            line = ""
            for word in words:
                test = line + word + " "
                if font.size(test)[0] > max_width:
                    if line:
                        lines.append(line.rstrip())
                    line = word + " "
                else:
                    line = test
            if line:
                lines.append(line.rstrip())
        return lines or [""]

    def draw(self, screen):
        """Draw the chat window."""
        if not self.visible:
            return

        self._ensure_fonts()

        panel_w = 520
        panel_h = SCREEN_HEIGHT - 100
        panel_x = 10
        panel_y = 50

        # Background
        surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surf.fill((15, 15, 25, 230))
        screen.blit(surf, (panel_x, panel_y))
        pygame.draw.rect(screen, (80, 80, 120),
                         (panel_x, panel_y, panel_w, panel_h), 1)

        # Title bar
        title_h = 24
        title_bg = pygame.Surface((panel_w - 2, title_h), pygame.SRCALPHA)
        title_bg.fill((30, 30, 50, 255))
        screen.blit(title_bg, (panel_x + 1, panel_y + 1))
        title = self._font_title.render("Claude Assistant (God Mode)", True, (200, 200, 255))
        screen.blit(title, (panel_x + 10, panel_y + 4))

        # Status indicator
        if not self.assistant.available:
            status_color = (200, 80, 80)
            status_text = "No API Key [K]"
        elif self.pending:
            status_color = (100, 200, 100)
            status_text = "Thinking..."
        else:
            status_color = (80, 180, 80)
            status_text = "Ready"
        status_surf = self._font_sm.render(status_text, True, status_color)
        screen.blit(status_surf, (panel_x + panel_w - status_surf.get_width() - 10,
                                  panel_y + 7))

        # Messages area
        msg_y_start = panel_y + title_h + 6
        msg_y_end = panel_y + panel_h - 68
        msg_area_h = msg_y_end - msg_y_start

        # Clip to message area
        clip_rect = pygame.Rect(panel_x, msg_y_start, panel_w, msg_area_h)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        # Render all messages and calculate total height
        rendered_lines = []
        for role, text in self.messages:
            if role == "user":
                prefix = "You: "
                color = (220, 220, 180)
            elif role == "system":
                prefix = ""
                color = (180, 180, 100)
            else:
                prefix = "Claude: "
                color = (180, 220, 255)

            full_text = prefix + text
            wrapped = self._wrap_text(full_text, panel_w - 30, self._font)
            for i, line in enumerate(wrapped):
                rendered_lines.append((line, color, role))
            rendered_lines.append(("", color, "gap"))  # gap between messages

        # Pending commands (show as buttons)
        cmd_lines = []
        if self.pending_commands:
            cmd_lines.append(("[Commands available - press Enter to execute all]",
                              (255, 200, 100)))
            for i, cmd in enumerate(self.pending_commands):
                cmd_lines.append((f"  [{i+1}] {cmd}", (200, 255, 180)))

        # Calculate total content height
        line_h = 15
        total_lines = len(rendered_lines) + len(cmd_lines)
        total_h = total_lines * line_h

        # Auto-scroll to bottom
        max_scroll = max(0, total_h - msg_area_h)
        if self.scroll_offset > max_scroll:
            self.scroll_offset = max_scroll

        # Draw messages
        y = msg_y_start - self.scroll_offset
        for line_text, color, role in rendered_lines:
            if line_text == "" and role == "gap":
                y += 4  # smaller gap
                continue
            if msg_y_start - line_h < y < msg_y_end:
                surf = self._font.render(line_text, True, color)
                screen.blit(surf, (panel_x + 10, y))
            y += line_h

        # Draw command buttons
        for cmd_text, cmd_color in cmd_lines:
            if msg_y_start - line_h < y < msg_y_end:
                surf = self._font.render(cmd_text, True, cmd_color)
                screen.blit(surf, (panel_x + 10, y))
            y += line_h

        screen.set_clip(old_clip)

        # Separator
        sep_y = panel_y + panel_h - 66
        pygame.draw.line(screen, (60, 60, 80),
                         (panel_x + 5, sep_y), (panel_x + panel_w - 5, sep_y))

        # Input box
        input_y = panel_y + panel_h - 58
        input_h = 24
        pygame.draw.rect(screen, (30, 30, 45),
                         (panel_x + 8, input_y, panel_w - 16, input_h))
        pygame.draw.rect(screen, (70, 70, 100),
                         (panel_x + 8, input_y, panel_w - 16, input_h), 1)

        if self.input_text:
            # Show the tail of the input if too long
            display = self.input_text
            max_chars = (panel_w - 30) // 8
            if len(display) > max_chars:
                display = "..." + display[-(max_chars - 3):]
            self.cursor_blink += 0.06
            if int(self.cursor_blink) % 2 == 0:
                display += "|"
            input_surf = self._font.render(display, True, (220, 220, 220))
            screen.blit(input_surf, (panel_x + 14, input_y + 5))
        else:
            hint = self._font.render("Ask Claude anything...", True, (90, 90, 110))
            screen.blit(hint, (panel_x + 14, input_y + 5))

        # Bottom hints
        hint_y = panel_y + panel_h - 30
        hints = "[Enter] Send  [Esc] Close  [K] API Key  [Ctrl+L] Clear"
        hint_surf = self._font_sm.render(hints, True, (120, 120, 140))
        screen.blit(hint_surf, (panel_x + 10, hint_y))

        # Scroll indicators
        if self.scroll_offset > 0:
            arrow = self._font_sm.render("^ scroll up (PgUp) ^", True, (100, 100, 140))
            screen.blit(arrow, (panel_x + panel_w // 2 - arrow.get_width() // 2,
                                msg_y_start))
        if self.scroll_offset < max_scroll:
            arrow = self._font_sm.render("v scroll down (PgDn) v", True, (100, 100, 140))
            screen.blit(arrow, (panel_x + panel_w // 2 - arrow.get_width() // 2,
                                msg_y_end - 12))

    def handle_event(self, event):
        """Handle pygame events when the chat is visible.

        Returns a list of commands, 'open_api_key_config', or None.
        """
        if not self.visible:
            return None

        if event.type == pygame.KEYDOWN:
            key = event.key

            if key == pygame.K_ESCAPE:
                self.visible = False
                return None

            if key == pygame.K_k and not self.input_text:
                # Signal to open API key config (handled by caller)
                return "open_api_key_config"

            if key == pygame.K_RETURN:
                # If there are pending commands, execute them
                if self.pending_commands and not self.input_text.strip():
                    cmds = list(self.pending_commands)
                    self.pending_commands.clear()
                    executed = []
                    for cmd in cmds:
                        result = self.god_console.execute(cmd)
                        executed.append(result)
                    self.messages.append(("system",
                                         "Executed: " + "; ".join(executed)))
                    self._auto_scroll()
                    return cmds

                # Otherwise send the message
                if self.input_text.strip() and not self.pending:
                    self._send_message()
                return None

            if key == pygame.K_BACKSPACE:
                if event.mod & pygame.KMOD_META or event.mod & pygame.KMOD_CTRL:
                    self.input_text = ""
                else:
                    self.input_text = self.input_text[:-1]
                return None

            if key == pygame.K_l and (event.mod & pygame.KMOD_META or
                                       event.mod & pygame.KMOD_CTRL):
                # Clear conversation
                self.messages.clear()
                self.pending_commands.clear()
                self.assistant.clear_conversation()
                self.scroll_offset = 0
                return None

            if key == pygame.K_PAGEUP:
                self.scroll_offset = max(0, self.scroll_offset - 100)
                return None

            if key == pygame.K_PAGEDOWN:
                self.scroll_offset += 100
                return None

            # Don't process other special keys as text
            return None

        if event.type == pygame.TEXTINPUT:
            self.input_text += event.text
            return None

        return None

    def _send_message(self):
        """Send current input text to Claude (async)."""
        text = self.input_text.strip()
        if not text:
            return

        self.messages.append(("user", text))
        self.input_text = ""
        self.pending = True
        self.pending_commands.clear()
        self._auto_scroll()

        def on_response(reply, commands):
            self.messages.append(("assistant", reply))
            self.pending_commands = commands
            self.pending = False
            self._auto_scroll()

        self.assistant.send_message_async(text, on_response)

    def _auto_scroll(self):
        """Scroll to bottom on new messages."""
        self.scroll_offset = 999999  # will be clamped in draw()


class APIKeyConfigUI:
    """Dialog for configuring the Anthropic API key."""

    def __init__(self):
        self.visible = False
        self.key_input = ""
        self.masked = True
        self.status_message = ""
        self.status_color = (150, 150, 170)
        self._fonts_ready = False
        self._font = None
        self._font_sm = None
        self._font_title = None

    def _ensure_fonts(self):
        if not self._fonts_ready:
            self._font = pygame.font.SysFont("monospace", 14)
            self._font_sm = pygame.font.SysFont("monospace", 11)
            self._font_title = pygame.font.SysFont("monospace", 16, bold=True)
            self._fonts_ready = True

    def show(self):
        self.visible = True
        self.key_input = ""
        self.status_message = ""
        # Check current key
        from game.ai.claude_assistant import get_api_key
        current = get_api_key()
        if current:
            self.status_message = f"Key configured ({current[:12]}...)"
            self.status_color = (100, 200, 100)
        else:
            self.status_message = "No key configured"
            self.status_color = (200, 100, 100)

    def draw(self, screen):
        """Draw the API key configuration dialog."""
        if not self.visible:
            return

        self._ensure_fonts()

        w, h = 550, 230
        x = (SCREEN_WIDTH - w) // 2
        y = (SCREEN_HEIGHT - h) // 2

        # Dimmed overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))

        # Dialog background
        pygame.draw.rect(screen, (20, 20, 35), (x, y, w, h))
        pygame.draw.rect(screen, (100, 100, 150), (x, y, w, h), 2)

        # Title
        title = self._font_title.render("Configure Anthropic API Key", True, WHITE)
        screen.blit(title, (x + 20, y + 15))

        # Instructions
        lines = [
            "Key is stored securely (system keychain or ~/.autonomous_world_key).",
            "Never stored in the game folder or committed to git.",
            "You can also set the ANTHROPIC_API_KEY environment variable.",
        ]
        iy = y + 42
        for line in lines:
            screen.blit(self._font_sm.render(line, True, (140, 140, 160)),
                        (x + 20, iy))
            iy += 15

        # Key input field
        input_y = y + 100
        pygame.draw.rect(screen, (40, 40, 55), (x + 20, input_y, w - 40, 28))
        pygame.draw.rect(screen, (80, 80, 110), (x + 20, input_y, w - 40, 28), 1)

        if self.key_input:
            display = "*" * len(self.key_input) if self.masked else self.key_input
            # Truncate display if too long
            max_chars = (w - 60) // 8
            if len(display) > max_chars:
                display = display[:max_chars - 3] + "..."
            key_surf = self._font.render(display, True, (220, 220, 220))
        else:
            key_surf = self._font.render("Paste API key here...", True, (90, 90, 110))
        screen.blit(key_surf, (x + 28, input_y + 6))

        # Buttons/hints
        hints_y = y + 140
        screen.blit(self._font_sm.render(
            "[Enter] Save    [Esc] Cancel    [Tab] Show/Hide key    [Del] Remove key",
            True, (170, 170, 190)), (x + 20, hints_y))

        # Status
        status_y = y + 170
        screen.blit(self._font.render(self.status_message, True, self.status_color),
                    (x + 20, status_y))

        # SDK check
        try:
            import anthropic
            sdk_msg = f"anthropic SDK: installed (v{getattr(anthropic, '__version__', '?')})"
            sdk_color = (100, 200, 100)
        except ImportError:
            sdk_msg = "anthropic SDK: NOT installed (pip install anthropic)"
            sdk_color = (200, 100, 100)
        screen.blit(self._font_sm.render(sdk_msg, True, sdk_color),
                    (x + 20, status_y + 22))

    def handle_event(self, event, assistant=None) -> Optional[str]:
        """Handle events. Returns 'saved', 'cancelled', 'deleted', or None."""
        if not self.visible:
            return None

        if event.type == pygame.KEYDOWN:
            key = event.key

            if key == pygame.K_ESCAPE:
                self.visible = False
                return "cancelled"

            if key == pygame.K_RETURN:
                if self.key_input.strip():
                    from game.ai.claude_assistant import store_api_key
                    if store_api_key(self.key_input.strip()):
                        self.status_message = "Key saved successfully!"
                        self.status_color = (100, 200, 100)
                        if assistant:
                            assistant.reconfigure(self.key_input.strip())
                        self.key_input = ""
                        self.visible = False
                        return "saved"
                    else:
                        self.status_message = "Failed to save key!"
                        self.status_color = (200, 100, 100)
                return None

            if key == pygame.K_TAB:
                self.masked = not self.masked
                return None

            if key == pygame.K_DELETE or key == pygame.K_F8:
                from game.ai.claude_assistant import delete_api_key
                delete_api_key()
                self.status_message = "Key removed."
                self.status_color = (200, 180, 100)
                if assistant:
                    assistant.api_key = None
                    assistant.available = False
                    assistant.client = None
                return "deleted"

            if key == pygame.K_BACKSPACE:
                self.key_input = self.key_input[:-1]
                return None

            # Paste support (Cmd+V / Ctrl+V)
            if key == pygame.K_v and (event.mod & pygame.KMOD_META or
                                       event.mod & pygame.KMOD_CTRL):
                try:
                    # Try pygame.scrap first
                    if not pygame.scrap.get_init():
                        pygame.scrap.init()
                    clipboard = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clipboard:
                        text = clipboard.decode('utf-8', errors='ignore').strip('\x00')
                        self.key_input += text
                except Exception:
                    # Fallback: try subprocess pbpaste on macOS
                    try:
                        import subprocess
                        result = subprocess.run(['pbpaste'], capture_output=True,
                                                text=True, timeout=2)
                        if result.returncode == 0 and result.stdout:
                            self.key_input += result.stdout.strip()
                    except Exception:
                        pass
                return None

            return None

        if event.type == pygame.TEXTINPUT:
            self.key_input += event.text
            return None

        return None

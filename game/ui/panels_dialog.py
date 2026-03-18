"""Dialog UI — conversation panels, free-text input."""

import pygame
from typing import Optional
from game.settings import *


class PanelsDialogMixin:

    """Mixin — see parent class for context."""

    def open_dialog(self, npc: NPC):
        self.dialog_active = True
        self.dialog_npc = npc
        self.dialog_key = "greeting"
        self.selected_response = 0
        self.llm_response_text = ""
        self.llm_waiting = False

    def open_text_input(self, npc: NPC):
        """Open free-text input to talk to NPC."""
        self.text_input_active = True
        self.text_input_buffer = ""
        self.dialog_npc = npc
        self.llm_response_text = ""
        self.llm_waiting = False

    def draw_dialog(self):
        if not self.dialog_active or not self.dialog_npc:
            return

        npc = self.dialog_npc
        dialog = npc.dialog_lines.get(self.dialog_key)
        if not dialog:
            self.dialog_active = False
            return

        dw, dh = 650, 280
        dx = SCREEN_WIDTH // 2 - dw // 2
        dy = SCREEN_HEIGHT - dh - 60

        title = f"{npc.name} - {getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)} Lv.{getattr(npc, 'level', 1)}"
        self._draw_panel(dx, dy, dw, dh, title)

        # NPC info line (needs, consciousness)
        info_parts = []
        if hasattr(npc, 'needs'):
            h = npc.needs.get("hunger", 0)
            if h < 40:
                info_parts.append(f"hungry({int(h)})")
        if npc.consciousness >= 2:
            info_parts.append(f"consciousness: {npc.consciousness}")
        if info_parts:
            info_str = "  ".join(info_parts)
            info_surf = self.font_sm.render(info_str, True, (120, 120, 160))
            self.screen.blit(info_surf, (dx + dw - info_surf.get_width() - 15, dy + 10))

        # NPC text (word-wrapped)
        text = dialog.text
        if self.llm_response_text:
            text = self.llm_response_text
        lines = self._wrap_text(text, dw - 30, self.font_md)
        y = dy + 42
        for line in lines[:6]:
            self.screen.blit(self.font_md.render(line, True, UI_TEXT), (dx + 15, y))
            y += 20

        # Response options
        responses = list(dialog.responses)
        # Add "Say something..." option
        responses.append(("Say something... (free text)", "free_text"))
        responses.append(("[Gift] Give an item...", "gift"))

        y = dy + dh - 15 - len(responses) * 22
        pygame.draw.line(self.screen, UI_BORDER, (dx + 5, y - 5), (dx + dw - 5, y - 5))

        for i, (response_text, _) in enumerate(responses):
            color = YELLOW if i == self.selected_response else UI_TEXT
            prefix = "> " if i == self.selected_response else "  "
            self.screen.blit(self.font_md.render(prefix + response_text, True, color), (dx + 15, y))
            y += 22

    def handle_dialog_input(self, key) -> Optional[str]:
        if not self.dialog_active or not self.dialog_npc:
            return None

        dialog = self.dialog_npc.dialog_lines.get(self.dialog_key)
        if not dialog:
            self.dialog_active = False
            return None

        responses = list(dialog.responses)
        responses.append(("Say something...", "free_text"))
        responses.append(("[Gift] Give an item...", "gift"))

        if key == pygame.K_UP:
            self.selected_response = max(0, self.selected_response - 1)
        elif key == pygame.K_DOWN:
            self.selected_response = min(len(responses) - 1, self.selected_response + 1)
        elif key == pygame.K_e or key == pygame.K_RETURN:
            if self.selected_response >= len(responses):
                return None

            _, next_key = responses[self.selected_response]

            if next_key == "free_text":
                self.dialog_active = False
                self.open_text_input(self.dialog_npc)
                return "free_text"
            elif next_key == "gift":
                self.dialog_active = False
                self.open_gift_panel(self.dialog_npc)
                return "gift"
            elif next_key == "goodbye":
                self.dialog_active = False
                return "close"
            elif next_key == "shop":
                self.dialog_active = False
                self.open_shop(self.dialog_npc)
                return "shop"
            else:
                self.dialog_key = next_key
                self.selected_response = 0
                return next_key
        elif key == pygame.K_ESCAPE:
            self.dialog_active = False
            return "close"
        elif key == pygame.K_t:
            self.dialog_active = False
            self.open_text_input(self.dialog_npc)
            return "free_text"

        return None

    # ================================================================
    # FREE TEXT INPUT
    # ================================================================

    def draw_text_input(self):
        """Draw the free-text input dialog."""
        if not self.text_input_active or not self.dialog_npc:
            return

        npc = self.dialog_npc
        dw, dh = 650, 300
        dx = SCREEN_WIDTH // 2 - dw // 2
        dy = SCREEN_HEIGHT - dh - 60

        self._draw_panel(dx, dy, dw, dh, f"Talking to {npc.name}")

        y = dy + 42

        # Show LLM response if available
        if self.llm_response_text:
            resp_lines = self._wrap_text(self.llm_response_text, dw - 30, self.font_md)
            name_surf = self.font_md.render(f"{npc.name}:", True, UI_HIGHLIGHT)
            self.screen.blit(name_surf, (dx + 15, y))
            y += 22
            for line in resp_lines[:6]:
                self.screen.blit(self.font_md.render(line, True, UI_TEXT), (dx + 25, y))
                y += 20
            y += 10
        elif self.llm_waiting:
            wait = self.font_md.render(f"{npc.name} is thinking...", True, (150, 150, 180))
            self.screen.blit(wait, (dx + 15, y))
            y += 30

        # Input field
        pygame.draw.line(self.screen, UI_BORDER, (dx + 5, dy + dh - 80), (dx + dw - 5, dy + dh - 80))
        prompt_label = self.font_md.render("You say:", True, YELLOW)
        self.screen.blit(prompt_label, (dx + 15, dy + dh - 68))

        # Text input box
        input_rect = pygame.Rect(dx + 15, dy + dh - 48, dw - 30, 26)
        pygame.draw.rect(self.screen, (30, 30, 45), input_rect)
        pygame.draw.rect(self.screen, UI_HIGHLIGHT, input_rect, 1)

        # Text with cursor
        display_text = self.text_input_buffer
        self.text_input_cursor_blink += 0.05
        if int(self.text_input_cursor_blink) % 2 == 0:
            display_text += "|"
        text_surf = self.font_md.render(display_text[-50:], True, WHITE)  # show last 50 chars
        self.screen.blit(text_surf, (dx + 20, dy + dh - 44))

        # Hints
        hint = self.font_sm.render("[Enter] Send  [Escape] Close  [Tab] Back to menu", True, (150, 150, 170))
        self.screen.blit(hint, (dx + dw // 2 - hint.get_width() // 2, dy + dh - 18))

    def handle_text_input_event(self, event) -> Optional[str]:
        """Handle events for text input. Returns 'send', 'close', 'back', or None."""
        if not self.text_input_active:
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.text_input_buffer.strip():
                    return "send"
            elif event.key == pygame.K_ESCAPE:
                self.text_input_active = False
                self.llm_response_text = ""
                return "close"
            elif event.key == pygame.K_TAB:
                # Go back to menu dialog
                self.text_input_active = False
                if self.dialog_npc:
                    self.open_dialog(self.dialog_npc)
                return "back"
            elif event.key == pygame.K_BACKSPACE:
                self.text_input_buffer = self.text_input_buffer[:-1]
            else:
                return None
        elif event.type == pygame.TEXTINPUT:
            self.text_input_buffer += event.text

        return None

    def get_and_clear_input(self) -> str:
        """Get the typed text and clear the buffer."""
        text = self.text_input_buffer.strip()
        self.text_input_buffer = ""
        return text

    def set_llm_response(self, text: str):
        """Set the LLM response to display."""
        self.llm_response_text = text
        self.llm_waiting = False

    # ================================================================
    # SHOP
    # ================================================================



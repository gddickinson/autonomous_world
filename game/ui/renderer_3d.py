"""3D OpenGL Renderer for the game world.

Provides the same interface as Renderer and AdventureRenderer so it can
be swapped in as the active renderer via _toggle_view_mode().

Uses PyOpenGL for hardware-accelerated polygon rendering with depth
buffering. Scene geometry is generated from world tiles by build_scene()
and compiled into OpenGL display lists for fast rendering.
"""

import math
import os

import pygame
from pygame.locals import DOUBLEBUF, OPENGL

from OpenGL.GL import *
from OpenGL.GLU import *

from game.settings import *


class Renderer3D:
    """Hardware-accelerated 3D renderer using OpenGL."""

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Camera parameters (from our test: az=15, el=-30 looked good)
        self.azimuth = 15.0      # degrees, horizontal rotation
        self.elevation = -30.0   # degrees, vertical tilt
        self.cam_dist = 18.0     # camera distance from player
        self.view_radius = 20    # tiles around player to render

        # Scene state
        self._gl_list = None     # compiled display list
        self._last_build_x = -999
        self._last_build_y = -999
        self._face_count = 0
        self._world_ref = None
        self._plan_ref = None

        # Fonts for HUD
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 16)

        # Particles (compatibility)
        self.particles = []

        # Initialize OpenGL state
        self._init_gl()

    def _init_gl(self):
        """Set up OpenGL state."""
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)  # winding is inconsistent
        glClearColor(0.53, 0.61, 0.76, 1.0)  # sky blue

    def set_world(self, world):
        """Store world reference for scene building."""
        self._world_ref = world
        self._plan_ref = getattr(world, 'plan', None)

    # ------------------------------------------------------------------
    # Camera controls (called from main.py key handler)
    # ------------------------------------------------------------------

    def rotate_camera(self, d_azimuth=0, d_elevation=0):
        self.azimuth += d_azimuth
        self.elevation = max(-80, min(-10, self.elevation + d_elevation))

    def zoom_camera(self, factor):
        self.cam_dist = max(5, min(50, self.cam_dist * factor))

    def change_radius(self, delta):
        self.view_radius = max(4, min(40, self.view_radius + delta))
        self._last_build_x = -999  # force rebuild

    # ------------------------------------------------------------------
    # Main rendering interface (matches Renderer / AdventureRenderer)
    # ------------------------------------------------------------------

    def draw_world(self, world, camera, visible_tiles=None, player=None):
        """Main render call — clear, set camera, draw scene."""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Perspective projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, self.screen_w / self.screen_h, 0.1, 200.0)

        # Camera look-at
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        az_rad = math.radians(self.azimuth)
        el_rad = math.radians(self.elevation)
        cam_x = self.cam_dist * math.sin(az_rad) * math.cos(el_rad)
        cam_y = self.cam_dist * -math.sin(el_rad)
        cam_z = self.cam_dist * math.cos(az_rad) * math.cos(el_rad)
        gluLookAt(cam_x, cam_y, cam_z, 0.5, 0.0, 0.5, 0.0, 1.0, 0.0)

        # Rebuild scene if player moved to a new tile or entered/left a building
        if player and self._world_ref:
            px, py = player.x, player.y
            cur_ix, cur_iy = int(px), int(py)
            cur_rect = getattr(player, '_current_building_rect', None)
            cur_floor = getattr(player, 'current_floor', 0)
            last_rect = getattr(self, '_last_building_rect', None)
            last_floor = getattr(self, '_last_floor', 0)
            if (cur_ix != self._last_build_x or cur_iy != self._last_build_y
                    or cur_rect != last_rect or cur_floor != last_floor):
                self._rebuild_scene(px, py, player)
                self._last_build_x, self._last_build_y = cur_ix, cur_iy
                self._last_building_rect = cur_rect
                self._last_floor = cur_floor

        # Draw compiled scene
        if self._gl_list:
            glCallList(self._gl_list)

    def _rebuild_scene(self, px, py, player=None):
        """Rebuild 3D geometry from world tiles around player."""
        from game.ui.scene_3d import build_scene

        player_rect = getattr(player, '_current_building_rect', None) if player else None
        player_fl = getattr(player, 'current_floor', 0) if player else 0
        faces = build_scene(self._world_ref, px, py,
                            self.view_radius, self._plan_ref,
                            player_building_rect=player_rect,
                            player_floor=player_fl)
        self._face_count = len(faces)

        # Compile into display list
        if self._gl_list:
            glDeleteLists(self._gl_list, 1)
        self._gl_list = self._compile_display_list(faces)

    def _compile_display_list(self, faces):
        """Compile face geometry into an OpenGL display list."""
        dl = glGenLists(1)
        glNewList(dl, GL_COMPILE)
        glBegin(GL_TRIANGLES)

        for verts, color, skip_cull in faces:
            r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
            glColor3f(r, g, b)

            if len(verts) >= 3:
                for i in range(1, len(verts) - 1):
                    v0, v1, v2 = verts[0], verts[i], verts[i + 1]
                    # Both windings for consistent visibility
                    glVertex3f(v0[0], v0[1], v0[2])
                    glVertex3f(v1[0], v1[1], v1[2])
                    glVertex3f(v2[0], v2[1], v2[2])
                    glVertex3f(v0[0], v0[1], v0[2])
                    glVertex3f(v2[0], v2[1], v2[2])
                    glVertex3f(v1[0], v1[1], v1[2])

        glEnd()
        glEndList()
        return dl

    def draw_player(self, player, camera):
        """Draw player as a yellow diamond at the origin."""
        glDisable(GL_CULL_FACE)
        size = 0.3
        cx, cy, cz = 0.5, 0.5, 0.5

        glBegin(GL_TRIANGLES)
        # Top half (bright yellow)
        glColor3f(0.9, 0.82, 0.25)
        for v0, v1 in [
            ((-size, 0, -size), (size, 0, -size)),
            ((size, 0, -size), (size, 0, size)),
            ((size, 0, size), (-size, 0, size)),
            ((-size, 0, size), (-size, 0, -size)),
        ]:
            glVertex3f(cx + v0[0], cy + size * 2, cz + v0[2])
            glVertex3f(cx + v0[0], cy, cz + v0[2])
            glVertex3f(cx + v1[0], cy, cz + v1[2])

        # Bottom half (darker)
        glColor3f(0.7, 0.65, 0.2)
        for v0, v1 in [
            ((-size, 0, -size), (size, 0, -size)),
            ((size, 0, -size), (size, 0, size)),
            ((size, 0, size), (-size, 0, size)),
            ((-size, 0, size), (-size, 0, -size)),
        ]:
            glVertex3f(cx, cy - size, cz)
            glVertex3f(cx + v1[0], cy, cz + v1[2])
            glVertex3f(cx + v0[0], cy, cz + v0[2])
        glEnd()

    def draw_creatures(self, creatures, camera, visible_tiles=None):
        """Draw creatures as small colored shapes."""
        if not creatures:
            return
        px = self._last_build_x
        py = self._last_build_y
        r2 = self.view_radius * self.view_radius

        glBegin(GL_TRIANGLES)
        for c in creatures:
            if not c.alive:
                continue
            dx = c.x - px
            dy = c.y - py
            if dx * dx + dy * dy > r2:
                continue

            # Color based on creature type
            cc = CREATURE_TYPES.get(c.kind, {}).get('color', (180, 60, 60))
            glColor3f(cc[0] / 255.0, cc[1] / 255.0, cc[2] / 255.0)

            wx, wz = c.x - px, c.y - py
            s = 0.2
            # Simple triangle marker
            glVertex3f(wx + 0.5, 0.6, wz + 0.5 - s)
            glVertex3f(wx + 0.5 - s, 0.1, wz + 0.5 + s)
            glVertex3f(wx + 0.5 + s, 0.1, wz + 0.5 + s)
        glEnd()

    def draw_npcs(self, npcs, camera, player=None, visible_tiles=None):
        """Draw NPCs as small colored shapes."""
        if not npcs:
            return
        px = self._last_build_x
        py = self._last_build_y
        r2 = self.view_radius * self.view_radius

        glBegin(GL_TRIANGLES)
        for npc in npcs:
            if not npc.alive:
                continue
            dx = npc.x - px
            dy = npc.y - py
            if dx * dx + dy * dy > r2:
                continue

            glColor3f(0.3, 0.5, 0.9)  # blue for NPCs
            wx, wz = npc.x - px, npc.y - py
            s = 0.2
            glVertex3f(wx + 0.5, 0.7, wz + 0.5 - s)
            glVertex3f(wx + 0.5 - s, 0.1, wz + 0.5 + s)
            glVertex3f(wx + 0.5 + s, 0.1, wz + 0.5 + s)
        glEnd()

    def draw_ground_items(self, items, camera):
        """Draw ground items as small bright dots."""
        if not items:
            return
        px = self._last_build_x
        py = self._last_build_y

        glPointSize(4)
        glBegin(GL_POINTS)
        glColor3f(0.9, 0.9, 0.3)
        for ix, iy, item in items:
            dx = ix - px
            dy = iy - py
            if dx * dx + dy * dy <= self.view_radius * self.view_radius:
                glVertex3f(dx + 0.5, 0.15, dy + 0.5)
        glEnd()

    def draw_night_overlay(self, darkness):
        """Draw a dark overlay for night time."""
        if darkness <= 0.01:
            return
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.screen_w, 0, self.screen_h, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        alpha = min(0.85, darkness * 0.9)
        glColor4f(0.0, 0.0, 0.05, alpha)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(self.screen_w, 0)
        glVertex2f(self.screen_w, self.screen_h)
        glVertex2f(0, self.screen_h)
        glEnd()

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    # ------------------------------------------------------------------
    # HUD / UI overlay helpers
    # ------------------------------------------------------------------

    def draw_hud(self, clock):
        """Draw FPS and camera info as text overlay."""
        fps = clock.get_fps()
        lines = [
            f"FPS: {fps:.0f}  Faces: {self._face_count}  "
            f"Radius: {self.view_radius}",
            f"Az: {self.azimuth:.0f}  El: {self.elevation:.0f}  "
            f"3D View (V to switch, Arrows to rotate)",
        ]
        self._draw_text_overlay(lines, 5, 5)

    def blit_surface(self, surface, x, y):
        """Blit a pygame surface onto the OpenGL framebuffer as a texture."""
        tex_data = pygame.image.tostring(surface, "RGBA", True)
        tw, th = surface.get_size()

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.screen_w, 0, self.screen_h, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, tex_data)

        glColor3f(1, 1, 1)
        gy = self.screen_h - y - th  # flip Y for OpenGL
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, gy)
        glTexCoord2f(1, 0); glVertex2f(x + tw, gy)
        glTexCoord2f(1, 1); glVertex2f(x + tw, gy + th)
        glTexCoord2f(0, 1); glVertex2f(x, gy + th)
        glEnd()

        glDeleteTextures([tex_id])
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    def _draw_text_overlay(self, lines, x, y):
        """Render text lines as a HUD overlay."""
        hud_h = len(lines) * 18 + 8
        hud_w = max(400, max(self.font_sm.size(l)[0] for l in lines) + 10)
        hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
        hud_surf.fill((0, 0, 0, 140))
        for i, txt in enumerate(lines):
            rendered = self.font_sm.render(txt, True, (240, 240, 250))
            hud_surf.blit(rendered, (5, 4 + i * 18))
        self.blit_surface(hud_surf, x, y)

    # ------------------------------------------------------------------
    # Stubs — not needed in 3D mode but called by main loop
    # ------------------------------------------------------------------

    def draw_building_doors(self, *args, **kwargs):
        pass

    def draw_structures(self, *args, **kwargs):
        pass

    def draw_world_events(self, *args, **kwargs):
        pass

    def draw_battle_visuals(self, *args, **kwargs):
        pass

    def draw_particles(self, camera, dt):
        # Update particle positions but don't render (could add GL particles later)
        self.particles = [(x, y, vx, vy, life - dt, color)
                          for x, y, vx, vy, life, color in self.particles
                          if life > 0]

    def draw_minimap(self, *args, **kwargs):
        pass  # could render minimap as 2D overlay later

    def build_minimap(self, *args, **kwargs):
        pass

    def update_minimap_explored(self, *args, **kwargs):
        pass

    def spawn_hit_particles(self, x, y):
        pass

    def spawn_xp_particles(self, x, y):
        pass

    def cleanup(self):
        """Free OpenGL resources."""
        if self._gl_list:
            glDeleteLists(self._gl_list, 1)
            self._gl_list = None

from __future__ import annotations
import pyray as rl

def inversion_curse(gc: Game_context, src_rect: rl.Rectangle) -> rl.Rectangle:
    """
    Applies the 'Inversion Curse' by calculating a flipped source rectangle.
    Returns a new Rectangle so we don't permanently mutate the original.
    """
    cursed_rect = rl.Rectangle(src_rect.x, src_rect.y, src_rect.width, src_rect.height)
    
    # Check if the curse is currently active
    if getattr(gc, "inversion_curse_active", False):
        # Flip Upside Down: raylib uses a negative height by default for render textures.
        # Making it positive flips it upside down.
        cursed_rect.height = abs(src_rect.height)
        
        # Optional: Uncomment the line below to ALSO flip the screen left-to-right
        cursed_rect.width = -abs(src_rect.width)
        
    return cursed_rect



def nausea_curse():
    pass

import pyray as rl
from pyray import Vector3
import math
import asyncio
import random
import time

def draw_grid(size=20, spacing=1.0):
    for i in range(-size, size + 1):
        rl.draw_line_3d(Vector3(i * spacing, 0, -size * spacing),
                        Vector3(i * spacing, 0, size * spacing),
                        rl.GRAY)
        rl.draw_line_3d(Vector3(-size * spacing, 0, i * spacing),
                        Vector3(size * spacing, 0, i * spacing),
                        rl.GRAY)

# --- Funcao de colisao entre duas caixas AABB ---
def check_collision(box1, box2):
    return (
        box1["min"].x <= box2["max"].x and box1["max"].x >= box2["min"].x and
        box1["min"].y <= box2["max"].y and box1["max"].y >= box2["min"].y and
        box1["min"].z <= box2["max"].z and box1["max"].z >= box2["min"].z
    )

def make_box(center, size):
    return {
        "min": Vector3(center.x - size.x/2, center.y - size.y/2, center.z - size.z/2),
        "max": Vector3(center.x + size.x/2, center.y + size.y/2, center.z + size.z/2)
    }

async def main():
    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
    rl.init_window(1000, 700, b"Cube Dodge 3D")
    rl.set_target_fps(60)
    rl.disable_cursor()

    # --- Jogador ---
    player_pos = Vector3(0, 1, 0)
    player_size = Vector3(1, 2, 1)
    player_speed = 0.2
    player_vel_y = 0
    on_ground = True
    lives = 5
    invulnerable_until = 0

    # --- Camera ---
    camera = rl.Camera3D()
    camera.up = Vector3(0, 1, 0)
    camera.fovy = 90
    camera_pitch = -0.3
    camera_yaw = 0
    third_person = False
    camera_distance = 6.0

    # --- Modelos ---
    model = rl.load_model(b"sword_2handed.gltf")
    enemy_model = rl.load_model(b"Mage.glb")

    cube_pos = rl.Vector3(0.0, 0.5, 0.0)  # centro do mapa, apoiado no chao
    sword_rotation_x = 0.0
    sword_rotation_y = 0.0


    # --- Inimigos ---
    enemies = []
    for i in range(3):
        enemies.append({
            "pos": Vector3(random.uniform(-10, 10), 1, random.uniform(-10, 10)),
            "dir": random.uniform(0, math.tau),
            "speed": 0.05,
            "cooldown": time.time() + random.uniform(1, 3)
        })

    # --- Projetis ---
    projectiles = []

    while not rl.window_should_close():
        now = time.time()
        # --- Alternar visao ---
        if rl.is_key_pressed(rl.KEY_F5):
            third_person = not third_person

        mouse_delta = rl.get_mouse_delta()
            # --- Rotacao da espada ---
        if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT):
            sword_rotation_y -= mouse_delta.x * 0.01
            sword_rotation_x -= mouse_delta.y * 0.01
        else:
            # --- Movimento da camera ---
            camera_yaw -= mouse_delta.x * 0.003
            camera_pitch -= mouse_delta.y * 0.003
        camera_pitch = max(-1.2, min(1.2, camera_pitch))

        dir_x = math.sin(camera_yaw) * math.cos(camera_pitch)
        dir_y = math.sin(camera_pitch)
        dir_z = math.cos(camera_yaw) * math.cos(camera_pitch)
        forward = Vector3(dir_x, dir_y, dir_z)
        right = Vector3(math.cos(camera_yaw), 0, -math.sin(camera_yaw))

        # --- Movimento do jogador ---
        move = Vector3(0, 0, 0)
        if rl.is_key_down(rl.KEY_W):
            move.x += forward.x
            move.z += forward.z
        if rl.is_key_down(rl.KEY_S):
            move.x -= forward.x
            move.z -= forward.z
        if rl.is_key_down(rl.KEY_A):
            move.x += right.x
            move.z += right.z
        if rl.is_key_down(rl.KEY_D):
            move.x -= right.x
            move.z -= right.z

        length = math.sqrt(move.x**2 + move.z**2)
        if length:
            move.x /= length
            move.z /= length

        player_pos.x += move.x * player_speed
        player_pos.z += move.z * player_speed

        # --- Pulo ---
        if rl.is_key_pressed(rl.KEY_SPACE) and on_ground:
            player_vel_y = 0.35
            on_ground = False

        player_vel_y -= 0.02
        player_pos.y += player_vel_y
        if player_pos.y <= 1:
            player_pos.y = 1
            player_vel_y = 0
            on_ground = True

        # --- Atualiza inimigos ---
        for enemy in enemies:
            enemy["pos"].x += math.cos(enemy["dir"]) * enemy["speed"]
            enemy["pos"].z += math.sin(enemy["dir"]) * enemy["speed"]
            if abs(enemy["pos"].x) > 19 or abs(enemy["pos"].z) > 19:
                enemy["dir"] += math.pi / 2
            if now >= enemy["cooldown"]:
                dir_to_player = Vector3(
                    player_pos.x - enemy["pos"].x,
                    0,
                    player_pos.z - enemy["pos"].z
                )
                d = math.sqrt(dir_to_player.x**2 + dir_to_player.z**2)
                if d != 0:
                    dir_to_player.x /= d
                    dir_to_player.z /= d
                projectiles.append({
                    "pos": Vector3(enemy["pos"].x, 1.5, enemy["pos"].z),
                    "vel": Vector3(dir_to_player.x * 0.3, 0, dir_to_player.z * 0.3),
                    "spawn": now
                })
                enemy["cooldown"] = now + random.uniform(2, 5)

        # --- Atualiza projetis ---
        new_projectiles = []
        for p in projectiles:
            p["pos"].x += p["vel"].x
            p["pos"].y += p["vel"].y
            p["pos"].z += p["vel"].z
            if now - p["spawn"] < 5:
                new_projectiles.append(p)
        projectiles = new_projectiles

        # --- Colisoes ---
        player_box = make_box(player_pos, player_size)

        if now > invulnerable_until:
            # Inimigos
            for enemy in enemies:
                enemy_box = make_box(enemy["pos"], Vector3(1, 2, 1))
                if check_collision(player_box, enemy_box):
                    lives -= 1
                    invulnerable_until = now + 3
                    break
            # Projetis
            new_projectiles = []
            for p in projectiles:
                proj_box = make_box(p["pos"], Vector3(0.5, 0.5, 0.5))
                if check_collision(player_box, proj_box):
                    lives -= 1
                    invulnerable_until = now + 3
                else:
                    new_projectiles.append(p)
            projectiles = new_projectiles

        # --- Camera ---
        if third_person:
            cam_offset = Vector3(-dir_x * camera_distance,
                                 -dir_y * camera_distance,
                                 -dir_z * camera_distance)
            camera.position = Vector3(
                player_pos.x + cam_offset.x,
                player_pos.y + 2 + cam_offset.y,
                player_pos.z + cam_offset.z
            )
        else:
            camera.position = Vector3(player_pos.x, player_pos.y + 1.5, player_pos.z)

        camera.target = Vector3(
            player_pos.x + dir_x,
            player_pos.y + 1.5 + dir_y,
            player_pos.z + dir_z
        )

        # --- Desenho ---
        rl.begin_drawing()
        rl.clear_background(rl.RAYWHITE)

        rl.begin_mode_3d(camera)
        draw_grid(20, 1.0)

        # Piscar quando invulneravel
        blink = (now * 10) % 2 < 1
        if now < invulnerable_until:
            if blink:
                rl.draw_cube(player_pos, 1, 2, 1, rl.BLUE)
        else:
            rl.draw_cube(player_pos, 1, 2, 1, rl.BLUE)

        for enemy in enemies:
            rl.draw_model(enemy_model, enemy["pos"], 1.0, rl.WHITE)
        for p in projectiles:
            rl.draw_sphere(p["pos"], 0.3, rl.ORANGE)
        # --- Espada ---
        model.transform = rl.matrix_multiply(
            rl.matrix_scale(1.0, 1.0, 1.0),
            rl.matrix_rotate_xyz(Vector3(sword_rotation_x, sword_rotation_y, 0.0))
        )
        rl.draw_model(model, cube_pos, 1.0, rl.WHITE)

        rl.end_mode_3d()



        # --- HUD ---
        # vidas como quadradinhos vermelhos
        for i in range(lives):
            x = 20 + i * 35
            y = 20
            rl.draw_rectangle(x, y, 30, 30, rl.RED)

        # invulnerabilidade
        if now < invulnerable_until:
            rl.draw_text("INVULNERAVEL", 20, 60, 25, rl.GOLD)

        rl.draw_text("F5 alterna visao", 10, 100, 20, rl.GRAY)

        rl.end_drawing()
        await asyncio.sleep(0)

    rl.unload_model(model)
    rl.unload_model(enemy_model)

    rl.close_window()

if __name__ == "__main__":
    asyncio.run(main())

# Pah rodah na webi usa isso aqui:
# python -m pygbag .
# e vai no http://localhost:8000/ 
# Effect meshes

The missile GLB is the editable source for the fixed attack-effect mesh.
It preserves the original Java-built geometry. Placement and animation remain
in the renderer, driven by the shared attack clock. Explosions, smoke and
projectile glows use shaders and need no sphere asset.

| File | Root group | Geometry |
|---|---|---|
| `missile-body.glb` | `missile-body-lod0` | Four triangles; closed missile body with per-face vertex colors |
| `arrow-iv.glb` | `arrow-iv-lod0` | 328 triangles; Arrow IV round with strakes and tail fins, per-face vertex colors |

The Arrow IV round is authored in metres, not board units: its base is at Y=0
and its nose tip at Y=4 (4 m long), 0.508 m across, twice its true thickness so
its band and fins still read at board zoom. The renderer scales it by the
board's metres and uses it for every Arrow IV shot, including an aircraft's
Arrow IV homing missile; without it those fly as the plain missile.

The missile has only LOD0. Preserve the group name when editing. Export rigid,
uncompressed GLB. It currently needs no texture.

The importer converts glTF Y-up into the game's Z-up coordinates. In game
coordinates the missile points along +Y, from its base at Y=0 to its tip at
Y=2.4; its three base corners lie on a
circle of radius 0.45 in the X/Z plane. The renderer rotates this template
along each flight path and batches its transformed vertices together.

## Explosion and smoke appearance

`GpuExplosionEffects` generates one unit cube for raster coverage and reuses
it for every volume. The visible fire and smoke come from `explosion.vert` /
`explosion.frag`. Size, location and wind stretch are shader uniforms, so the
coverage geometry is never rebuilt for individual blasts or animation frames.

The shader integrates animated density and emission along each viewing ray,
with a cooling fire core, local smoke self-shadowing, atmosphere lighting and
opaque scene-depth clipping. It supports orthographic and perspective views,
including a camera inside the volume. The renderer owns and disposes its
coverage mesh, depth snapshot and shader; it never samples the active
framebuffer's attached depth texture. Board wind direction and strength drive
downwind drift, stretching, internal advection and thinning as the blast cools.
Time comes from attack playback, so pausing does not evolve the effect.

At most 128 volumes are drawn, using 32 integration steps per ray and two
short light samples. Large-battle frame-time impact has not been benchmarked.
This is a procedural visual effect without fluid simulation or light cast
onto surrounding objects. Missile trails and flame jets retain their existing
bounded quad batches. Tracers, energy balls, flares, sprays, screens and
contact glows now use `projectiles.frag` in the same shared quad renderer.
Its mesh, indices and CPU vertex storage are allocated once and reused;
animated positions and phases are updated per frame.

Ballistic contacts produce only shader spark streaks and a brief contact glint,
with no impact fire or smoke. Count increases with rack size, from 6 sparks for
an AC/2 to 24 for an AC/20 (at most 32 per contact). Spark width and travel scale
with the square root of rack size. Every MG round has a separate 130 ms pulse
in both normal and rapid-fire modes; missiles retain their explosions. Battle Armor and other
solid targets spark; conventional-infantry body hits do not. Terrain misses
spark only on identified rock/concrete surfaces, rock outcrops or detached
mech parts; soft ground, water, ice, vegetation and unknown props do not.
The existing geometry picker supplies that material, cached once per impact.
Spark motion, cooling and fade share the attack clock.

`GpuExplosionSmokeTest` checks both cameras, cooling, wind response,
paused-frame repeatability, opaque occlusion and near/far clipping.
`GpuProjectileSmokeTest` checks projectile appearance, animation, occlusion,
end-on tracers, spark count and size by rack size, and successive MG impacts in both modes,
including infantry and terrain exceptions and retained missile explosions.
Geometry and event-capture tests verify surface and unit classification.
Volley, machine-gun and defensive playback tests cover attack integration.

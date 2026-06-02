import os
from pathlib import Path

# Directory names (any depth under Assets/) that are skipped entirely.
# These are Unity built-ins and common third-party packages that add noise
# without belonging to the user's own project code.
EXCLUDED_DIRS: frozenset[str] = frozenset({
    # Unity built-in / package cache
    "Plugins",
    "Standard Assets",
    "StreamingAssets",
    "Editor Default Resources",
    "Gizmos",
    "XR",
    # TextMeshPro
    "TextMesh Pro",
    # Common third-party assets
    "DOTween",
    "Cinemachine",
    "Post Processing",
    "ProBuilder Data",
    "Photon",
    "Photon Unity Networking",
    "Mirror",
    "NavMeshComponents",
    "Feel",
    "NaughtyAttributes",
    "Odin Inspector",
    "Rewired",
    "PlayFab",
    "Firebase",
    "GoogleMobileAds",
    "UnityPurchasing",
    "I2",
    "NodeCanvas",
    "Spine",
    "FlatKit",
    "AmplifyShaderEditor",
    "Bakery",
    "FMOD",
    "Wwise",
})


def iter_assets(project_root: str, suffix: str):
    """Yield Path objects for files ending with *suffix* under Assets/,
    skipping any directory in EXCLUDED_DIRS."""
    assets = Path(project_root) / "Assets"
    if not assets.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(assets):
        # Prune in-place so os.walk never descends into excluded dirs
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            if fname.endswith(suffix):
                yield Path(dirpath) / fname

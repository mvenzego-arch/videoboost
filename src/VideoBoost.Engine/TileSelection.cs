namespace VideoBoost.Engine;

public enum TileMode { Preset, Auto, Fixed256, Fixed384, Fixed512 }

/// <summary>Разрешение tile: режимы preset/auto и фикс-значения; гарантия 128..640 — legacy _resolve_tile.</summary>
public static class TileSelection
{
    public static int Resolve(TileMode mode, Preset preset, int scale)
    {
        var tile = mode switch
        {
            TileMode.Fixed256 => 256,
            TileMode.Fixed384 => 384,
            TileMode.Fixed512 => 512,
            _ => preset.Tile,
        };
        if (mode is TileMode.Preset or TileMode.Auto && scale >= 3 && tile < 384)
        {
            tile = 384; // крупный tile для больших кадров
        }
        return Math.Max(128, Math.Min(640, tile));
    }
}

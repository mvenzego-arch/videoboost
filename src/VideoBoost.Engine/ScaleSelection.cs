namespace VideoBoost.Engine;

public enum ScaleMode { Preset, X1, X2, X3, X4, Auto2160, Auto4320 }

/// <summary>Итоговый масштаб: из настроек, пресета или «авто до 4K/8K» (legacy _resolve_scale).</summary>
public static class ScaleSelection
{
    public static int Resolve(ScaleMode mode, Preset preset, int videoHeight) => mode switch
    {
        ScaleMode.X1 => 1,
        ScaleMode.X2 => 2,
        ScaleMode.X3 => 3,
        ScaleMode.X4 => 4,
        ScaleMode.Auto2160 => AutoByHeight(2160, preset, videoHeight),
        ScaleMode.Auto4320 => AutoByHeight(4320, preset, videoHeight),
        _ => Math.Max(1, preset.Scale),
    };

    private static int AutoByHeight(int target, Preset preset, int videoHeight)
    {
        if (videoHeight <= 0)
        {
            return Math.Max(1, preset.Scale);
        }
        if (videoHeight >= target)
        {
            return 1; // уже не ниже цели — апскейл не нужен
        }
        var needed = (int)Math.Ceiling((double)target / Math.Max(1, videoHeight));
        return Math.Max(2, Math.Min(4, needed));
    }
}

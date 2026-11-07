namespace VideoBoost.Engine;

/// <summary>Вспомогательные конфорки форматов кадров для билдеров команд.</summary>
public static class EngineFormats
{
    public static string Ext(FrameFormat format) => format switch
    {
        FrameFormat.Png => "png",
        _ => "jpg",
    };
}

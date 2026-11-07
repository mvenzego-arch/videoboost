namespace VideoBoost.Engine;

/// <summary>Формат промежуточных кадров. Jpg — экономия диска (legacy: save_space по умолчанию).</summary>
public enum FrameFormat { Jpg, Png }

public enum QualityKind { Speed, Balanced, Quality }

public enum EncoderKind { AmfH264, AmfHevc, Cpu }

public enum ContentKind { General, Anime }

public enum ModelMode { Auto, Light, Heavy }

/// <summary>Пресет — числа перенесены из legacy engine.py (ветка legacy-python).</summary>
public sealed record Preset(
    string Key,
    string Title,
    int Scale,
    bool Interpolate,
    int TargetFps,
    EncoderKind Encoder,
    QualityKind Quality,
    int Tile,
    string Description);

public static class Presets
{
    public static readonly Preset Fast = new(
        Key: "fast",
        Title: "Быстро",
        Scale: 2,
        Interpolate: false,
        TargetFps: 60,
        Encoder: EncoderKind.AmfH264,
        Quality: QualityKind.Speed,
        Tile: 256,
        Description: "Апскейл x2 (1080p → 4K) лёгкой моделью, H.264 на GPU, без интерполяции. "
            + "Самый быстрый вариант: ~1 час на 1 минуту видео 1080p.");

    public static readonly Preset Balanced = new(
        Key: "balanced",
        Title: "Баланс",
        Scale: 2,
        Interpolate: true,
        TargetFps: 60,
        Encoder: EncoderKind.AmfHevc,
        Quality: QualityKind.Balanced,
        Tile: 384,
        Description: "Апскейл x2 (1080p → 4K) + плавность до 60 FPS, HEVC. "
            + "Оптимальный выбор: ~1–2 часа на 1 минуту видео 1080p.");

    public static readonly Preset Max = new(
        Key: "max",
        Title: "Максимально",
        Scale: 4,
        Interpolate: true,
        TargetFps: 60,
        Encoder: EncoderKind.AmfHevc,
        Quality: QualityKind.Quality,
        Tile: 512,
        Description: "Апскейл x4 (1080p → 8K!) тяжёлой моделью + 60 FPS, максимум качества. "
            + "На RX 570 очень медленно: десятки часов на 1 минуту видео.");

    public static Preset ByKey(string key) => key switch
    {
        _ when key == Fast.Key => Fast,
        _ when key == Balanced.Key => Balanced,
        _ when key == Max.Key => Max,
        _ => throw new ArgumentOutOfRangeException(nameof(key), key, "Неизвестный пресет"),
    };

    /// <summary>Качество кодирования: (qp для AMF, crf для libx264) — legacy QUALITY_LEVELS.</summary>
    public static (int Qp, int Crf) QualityLevels(QualityKind kind) => kind switch
    {
        QualityKind.Speed => (26, 23),
        QualityKind.Quality => (19, 18),
        _ => (22, 21),
    };
}

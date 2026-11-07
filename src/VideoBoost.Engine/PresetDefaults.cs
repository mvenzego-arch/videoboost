using System.Collections.ObjectModel;

namespace VideoBoost.Engine;

/// <summary>
/// Дефолты трёх пресетов, перенесённые из legacy <c>engine.py</c> (ветка
/// <c>legacy-python</c>, словарь <c>PRESETS</c>). Числа и описания совпадают с
/// доказанной Python-версией.
/// </summary>
public static class PresetDefaults
{
    /// <summary>«Быстро»: x2 лёгкой моделью, без интерполяции, H.264 AMF, Speed, tile 256.</summary>
    public static PresetDefinition Fast { get; } = new(
        PresetKind.Fast,
        "Быстро",
        ScaleMode.X2,
        ModelMode.Light,
        Interpolate: false,
        FpsMode.Fps60,
        EncoderMode.AmfH264,
        QualityMode.Speed,
        TileMode.T256,
        SaveSpace: true,
        "Апскейл x2 (1080p → 4K) лёгкой моделью, H.264 на GPU, без интерполяции. "
            + "Самый быстрый вариант: ~1 час на 1 минуту видео 1080p.");

    /// <summary>«Баланс»: x2 лёгкой моделью, 60 FPS, HEVC AMF, Balanced, tile 384.</summary>
    public static PresetDefinition Balanced { get; } = new(
        PresetKind.Balanced,
        "Баланс",
        ScaleMode.X2,
        ModelMode.Light,
        Interpolate: true,
        FpsMode.Fps60,
        EncoderMode.AmfHevc,
        QualityMode.Balanced,
        TileMode.T384,
        SaveSpace: true,
        "Апскейл x2 (1080p → 4K) + плавность до 60 FPS, HEVC. "
            + "Оптимальный выбор: ~1–2 часа на 1 минуту видео 1080p.");

    /// <summary>«Максимально»: x4 тяжёлой моделью, 60 FPS, HEVC AMF, Max, tile 512.</summary>
    public static PresetDefinition Max { get; } = new(
        PresetKind.Max,
        "Максимально",
        ScaleMode.X4,
        ModelMode.Heavy,
        Interpolate: true,
        FpsMode.Fps60,
        EncoderMode.AmfHevc,
        QualityMode.Max,
        TileMode.T512,
        SaveSpace: true,
        "Апскейл x4 (1080p → 8K!) тяжёлой моделью + 60 FPS, максимум качества. "
            + "На RX 570 очень медленно: десятки часов на 1 минуту видео.");

    /// <summary>Все пресеты в порядке legacy: «Быстро», «Баланс», «Максимально».</summary>
    public static IReadOnlyList<PresetDefinition> All { get; } =
        new ReadOnlyCollection<PresetDefinition>([Fast, Balanced, Max]);

    /// <summary>Возвращает описание пресета по его идентификатору.</summary>
    /// <param name="kind">Идентификатор пресета.</param>
    /// <returns>Неизменяемое описание пресета с дефолтами из legacy.</returns>
    /// <exception cref="ArgumentOutOfRangeException">Идентификатор пресета неизвестен.</exception>
    public static PresetDefinition For(PresetKind kind) => kind switch
    {
        PresetKind.Fast => Fast,
        PresetKind.Balanced => Balanced,
        PresetKind.Max => Max,
        _ => throw new ArgumentOutOfRangeException(nameof(kind), kind, "Неизвестный пресет."),
    };
}

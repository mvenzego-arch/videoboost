namespace VideoBoost.Engine;

/// <summary>
/// Пользовательские настройки прогона с «override»-семантикой: <see langword="null"/>
/// означает «взять из пресета», заданное значение перекрывает пресет. Соответствует
/// legacy <c>Settings</c>, где <c>preset</c>/<c>auto</c> были отдельными значениями.
/// </summary>
/// <param name="Preset">Пресет по умолчанию для <see cref="Resolve()"/>.</param>
/// <param name="Scale">Масштаб; <see langword="null"/> — из пресета.</param>
/// <param name="Model">Модель; <see langword="null"/> — из пресета.</param>
/// <param name="Interpolate">Интерполяция; <see langword="null"/> — из пресета.</param>
/// <param name="Fps">Целевая частота; <see langword="null"/> — из пресета.</param>
/// <param name="Content">Тип содержимого; <see langword="null"/> — General.</param>
/// <param name="Encoder">Кодировщик; <see langword="null"/> или <see cref="EncoderMode.Auto"/> — из пресета.</param>
/// <param name="Quality">Качество; <see langword="null"/> или <see cref="QualityMode.Auto"/> — из пресета.</param>
/// <param name="Tile">Tile; <see langword="null"/> или <see cref="TileMode.Auto"/> — из пресета (с повышением при x3/x4).</param>
/// <param name="SaveSpace">JPEG-промежутки; <see langword="null"/> — из пресета.</param>
public sealed record RunSettings(
    PresetKind Preset = PresetKind.Balanced,
    ScaleMode? Scale = null,
    ModelMode? Model = null,
    bool? Interpolate = null,
    FpsMode? Fps = null,
    ContentKind? Content = null,
    EncoderMode? Encoder = null,
    QualityMode? Quality = null,
    TileMode? Tile = null,
    bool? SaveSpace = null)
{
    /// <summary>
    /// Применяет указанный пресет и все заданные overrides, возвращая эффективные
    /// настройки без запуска процессов.
    /// </summary>
    /// <param name="preset">Базовый пресет, из которого берутся незаданные значения.</param>
    /// <returns>Эффективные настройки, эквивалентные legacy-резолверу.</returns>
    /// <exception cref="ArgumentOutOfRangeException">Идентификатор пресета неизвестен.</exception>
    public ResolvedSettings Resolve(PresetKind preset)
    {
        var defaults = PresetDefaults.For(preset);

        var encoder = Encoder is null or EncoderMode.Auto ? defaults.Encoder : Encoder.Value;
        var quality = Quality is null or QualityMode.Auto ? defaults.Quality : Quality.Value;

        return new ResolvedSettings(
            preset,
            defaults.Title,
            defaults.Description,
            Scale ?? defaults.Scale,
            Model ?? defaults.Model,
            Interpolate ?? defaults.Interpolate,
            Fps ?? defaults.Fps,
            Content ?? ContentKind.General,
            encoder,
            quality,
            Tile ?? defaults.Tile,
            SaveSpace ?? defaults.SaveSpace,
            TileFromPreset: Tile is null or TileMode.Auto);
    }

    /// <summary>Применяет пресет из <see cref="Preset"/> и заданные overrides.</summary>
    /// <returns>Эффективные настройки.</returns>
    public ResolvedSettings Resolve() => Resolve(Preset);
}

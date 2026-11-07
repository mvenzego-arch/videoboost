namespace VideoBoost.Engine;

/// <summary>
/// Эффективные настройки после применения пресета и пользовательских overrides.
/// Значения соответствуют legacy-резолверам <c>_resolve_scale/_resolve_model/
/// _resolve_tile/_resolve_quality/_resolve_encoder</c>, но без запуска процессов.
/// </summary>
/// <param name="Preset">Пресет, из которого взяты значения по умолчанию.</param>
/// <param name="PresetTitle">Подпись пресета для интерфейса.</param>
/// <param name="PresetDescription">Описание пресета из legacy.</param>
/// <param name="Scale">Эффективный режим масштаба; <see cref="ScaleMode.Auto2160"/>/<see cref="ScaleMode.Auto4320"/> разрешаются через <see cref="ResolveScale"/>.</param>
/// <param name="Model">Эффективный режим модели; <see cref="ModelMode.Auto"/> разрешается через <see cref="ResolveModel"/>.</param>
/// <param name="Interpolate">Включена ли интерполяция кадров.</param>
/// <param name="Fps">Целевая частота кадров.</param>
/// <param name="Content">Тип содержимого.</param>
/// <param name="Encoder">Эффективный кодировщик (никогда не <see cref="EncoderMode.Auto"/>).</param>
/// <param name="Quality">Эффективное качество (никогда не <see cref="QualityMode.Auto"/>).</param>
/// <param name="Tile">Эффективный режим tile; <see cref="TileMode.Auto"/> разрешается через <see cref="ResolveTile"/>.</param>
/// <param name="SaveSpace">Хранить промежуточные кадры в JPEG.</param>
/// <param name="TileFromPreset">
/// Tile взят из пресета или режима Auto (а не задан явно): при масштабе x3/x4
/// legacy повышает его до 384. Флаг не влияет на отображение режима.
/// </param>
public sealed record ResolvedSettings(
    PresetKind Preset,
    string PresetTitle,
    string PresetDescription,
    ScaleMode Scale,
    ModelMode Model,
    bool Interpolate,
    FpsMode Fps,
    ContentKind Content,
    EncoderMode Encoder,
    QualityMode Quality,
    TileMode Tile,
    bool SaveSpace,
    bool TileFromPreset)
{
    /// <summary>Целевая частота кадров числом (60 или 120).</summary>
    public int TargetFps => (int)Fps;

    /// <summary>
    /// Итоговый множитель масштаба. Для фиксированных режимов — 2/3/4; для
    /// auto-режимов — минимальный множитель 2..4, закрывающий высоту до 2160p/4320p
    /// (1, если источник уже не ниже цели). При неизвестной высоте (&lt;= 0)
    /// возвращается масштаб пресета — как в legacy <c>_resolve_scale</c>.
    /// </summary>
    /// <param name="sourceHeight">Высота исходного кадра; 0 — неизвестна.</param>
    /// <returns>Множитель масштаба 1..4.</returns>
    public int ResolveScale(int sourceHeight) => Scale switch
    {
        ScaleMode.X2 => 2,
        ScaleMode.X3 => 3,
        ScaleMode.X4 => 4,
        ScaleMode.Auto2160 => ResolveAutoScale(2160, sourceHeight),
        ScaleMode.Auto4320 => ResolveAutoScale(4320, sourceHeight),
        _ => throw new InvalidOperationException($"Неизвестный режим масштаба {Scale}."),
    };

    /// <summary>
    /// Имя модели Real-ESRGAN для аргумента <c>-n</c>. Тяжёлая модель допустима
    /// только при масштабе x4; <see cref="ModelMode.Auto"/> выбирает тяжёлую лишь
    /// для пресета «Максимально». Точная копия legacy <c>_resolve_model</c>.
    /// </summary>
    /// <param name="scale">Итоговый множитель масштаба (см. <see cref="ResolveScale"/>).</param>
    /// <returns>Имя модели: <c>realesr-animevideov3</c>, <c>realesrgan-x4plus</c> или <c>realesrgan-x4plus-anime</c>.</returns>
    public string ResolveModel(int scale)
    {
        var heavy = Model switch
        {
            ModelMode.Heavy => true,
            ModelMode.Auto => Preset == PresetKind.Max,
            _ => false,
        };

        if (scale < 4)
        {
            heavy = false;
        }

        if (!heavy)
        {
            return ModelNames.Light;
        }

        return Content == ContentKind.Anime ? ModelNames.HeavyAnime : ModelNames.Heavy;
    }

    /// <summary>
    /// Итоговый tile Real-ESRGAN. Явно выбранный t256/t384/t512 сохраняется;
    /// значение из пресета или <see cref="TileMode.Auto"/> при масштабе x3/x4
    /// повышается минимум до 384 (legacy <c>_resolve_tile</c>). Результат
    /// ограничен диапазоном 128..640.
    /// </summary>
    /// <param name="scale">Итоговый множитель масштаба (см. <see cref="ResolveScale"/>).</param>
    /// <returns>Размер tile в пикселях.</returns>
    public int ResolveTile(int scale)
    {
        var tile = Tile switch
        {
            TileMode.T256 => 256,
            TileMode.T384 => 384,
            TileMode.T512 => 512,
            _ => NumericPresetTile(),
        };

        if (TileFromPreset && scale >= 3 && tile < 384)
        {
            tile = 384;
        }

        return Math.Clamp(tile, 128, 640);
    }

    /// <summary>Параметры качества кодирования для эффективного <see cref="Quality"/>.</summary>
    /// <returns>QP для AMF и CRF для libx264.</returns>
    public (int Qp, int Crf) GetQualityLevels() => QualityLevels.For(Quality);

    private int ResolveAutoScale(int targetHeight, int sourceHeight)
    {
        if (sourceHeight <= 0)
        {
            return PresetDefaults.For(Preset).ScaleFactor;
        }

        if (sourceHeight >= targetHeight)
        {
            return 1;
        }

        var needed = (int)Math.Ceiling(targetHeight / (double)sourceHeight);
        return Math.Clamp(needed, 2, 4);
    }

    private int NumericPresetTile() => PresetDefaults.For(Preset).Tile switch
    {
        TileMode.T256 => 256,
        TileMode.T384 => 384,
        TileMode.T512 => 512,
        _ => throw new InvalidOperationException(
            $"Пресет {Preset} должен задавать фиксированный tile."),
    };
}

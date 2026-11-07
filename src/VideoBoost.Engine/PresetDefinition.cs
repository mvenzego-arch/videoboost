namespace VideoBoost.Engine;

/// <summary>
/// Неизменяемое описание пресета обработки: значения по умолчанию, которые
/// подставляются, если пользователь не переопределил настройку.
/// </summary>
/// <param name="Kind">Идентификатор пресета.</param>
/// <param name="Title">Подпись для интерфейса («Быстро», «Баланс», «Максимально»).</param>
/// <param name="Scale">Масштаб апскейла по умолчанию.</param>
/// <param name="Model">Модель по умолчанию (лёгкая/тяжёлая), выведенная из legacy <c>_resolve_model</c>.</param>
/// <param name="Interpolate">Включена ли интерполяция кадров по умолчанию.</param>
/// <param name="Fps">Целевая частота кадров по умолчанию.</param>
/// <param name="Encoder">Кодировщик по умолчанию.</param>
/// <param name="Quality">Качество кодирования по умолчанию.</param>
/// <param name="Tile">Tile Real-ESRGAN по умолчанию.</param>
/// <param name="SaveSpace">Хранить промежуточные кадры в JPEG (экономия диска).</param>
/// <param name="Description">Текст описания пресета из legacy <c>PRESETS</c>.</param>
public sealed record PresetDefinition(
    PresetKind Kind,
    string Title,
    ScaleMode Scale,
    ModelMode Model,
    bool Interpolate,
    FpsMode Fps,
    EncoderMode Encoder,
    QualityMode Quality,
    TileMode Tile,
    bool SaveSpace,
    string Description)
{
    /// <summary>Целевая частота кадров числом (60 или 120).</summary>
    public int TargetFps => (int)Fps;

    /// <summary>
    /// Числовой множитель масштаба для фиксированных режимов (<see cref="ScaleMode.X2"/>,
    /// <see cref="ScaleMode.X3"/>, <see cref="ScaleMode.X4"/>). Пресеты используют только их.
    /// </summary>
    /// <exception cref="InvalidOperationException">Режим масштаба не фиксированный.</exception>
    public int ScaleFactor => Scale switch
    {
        ScaleMode.X2 => 2,
        ScaleMode.X3 => 3,
        ScaleMode.X4 => 4,
        _ => throw new InvalidOperationException(
            $"Пресет {Kind} не может использовать автоматический масштаб {Scale}."),
    };
}

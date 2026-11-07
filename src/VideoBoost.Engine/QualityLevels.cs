namespace VideoBoost.Engine;

/// <summary>
/// Таблица качества кодирования из legacy <c>QUALITY_LEVELS</c>: пара «QP для AMF,
/// CRF для libx264».
/// </summary>
public static class QualityLevels
{
    /// <summary>
    /// Возвращает параметры качества для выбранного режима.
    /// <see cref="QualityMode.Auto"/> и <see cref="QualityMode.Balanced"/> дают
    /// сбалансированные значения (26/23 — Speed, 22/21 — Balanced, 19/18 — Max).
    /// </summary>
    /// <param name="quality">Режим качества; <see cref="QualityMode.Auto"/> трактуется как Balanced.</param>
    /// <returns>Пара QP для AMF и CRF для libx264.</returns>
    public static (int Qp, int Crf) For(QualityMode quality) => quality switch
    {
        QualityMode.Speed => (26, 23),
        QualityMode.Max => (19, 18),
        _ => (22, 21),
    };
}

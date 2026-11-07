namespace VideoBoost.Engine;

/// <summary>
/// Режим масштабирования: фиксированный множитель x2/x3/x4 либо автоматический
/// подбор под высоту 2160p (4K) или 4320p (8K). Соответствует legacy
/// <c>scale_mode</c> (<c>preset | x2 | x3 | x4 | auto_2160 | auto_4320</c>).
/// </summary>
public enum ScaleMode
{
    /// <summary>Увеличить кадр в 2 раза.</summary>
    X2,

    /// <summary>Увеличить кадр в 3 раза.</summary>
    X3,

    /// <summary>Увеличить кадр в 4 раза.</summary>
    X4,

    /// <summary>Автоматически подобрать множитель до высоты 2160p (не более x4).</summary>
    Auto2160,

    /// <summary>Автоматически подобрать множитель до высоты 4320p (не более x4).</summary>
    Auto4320,
}

/// <summary>
/// Режим выбора модели Real-ESRGAN. Соответствует legacy <c>model_mode</c>
/// (<c>auto | light | heavy</c>). Тяжёлая модель работает только при масштабе x4.
/// </summary>
public enum ModelMode
{
    /// <summary>Как в пресете: «Быстро»/«Баланс» — лёгкая, «Максимально» — тяжёлая.</summary>
    Auto,

    /// <summary>Лёгкая быстрая модель <c>realesr-animevideov3</c>.</summary>
    Light,

    /// <summary>Тяжёлая модель <c>realesrgan-x4plus</c> (или аниме-вариант); только x4.</summary>
    Heavy,
}

/// <summary>
/// Целевая частота кадров после интерполяции. Соответствует legacy <c>target_fps</c>
/// (60 или 120). Числовые значения намеренно равны самой частоте.
/// </summary>
public enum FpsMode
{
    /// <summary>60 кадров в секунду.</summary>
    Fps60 = 60,

    /// <summary>120 кадров в секунду.</summary>
    Fps120 = 120,
}

/// <summary>
/// Тип содержимого видео. Соответствует legacy <c>content</c>
/// (<c>general | anime</c>) и влияет только на выбор тяжёлой модели.
/// </summary>
public enum ContentKind
{
    /// <summary>Обычное видео — <c>realesrgan-x4plus</c> для тяжёлой модели.</summary>
    General,

    /// <summary>Аниме — <c>realesrgan-x4plus-anime</c> для тяжёлой модели.</summary>
    Anime,
}

/// <summary>
/// Режим видеокодировщика. Соответствует legacy <c>encoder_mode</c>
/// (<c>preset | amf_h264 | amf_hevc | cpu</c>); <see cref="Auto"/> означает
/// «взять из пресета».
/// </summary>
public enum EncoderMode
{
    /// <summary>Взять кодировщик из выбранного пресета.</summary>
    Auto,

    /// <summary>AMD AMF H.264 (<c>h264_amf</c>).</summary>
    AmfH264,

    /// <summary>AMD AMF HEVC (<c>hevc_amf</c>).</summary>
    AmfHevc,

    /// <summary>Программный <c>libx264</c>.</summary>
    Cpu,
}

/// <summary>
/// Уровень качества кодирования. Соответствует legacy <c>quality</c>
/// (<c>preset | speed | balanced | quality</c>); <see cref="Auto"/> означает
/// «взять из пресета».
/// </summary>
public enum QualityMode
{
    /// <summary>Взять качество из выбранного пресета.</summary>
    Auto,

    /// <summary>Быстрый режим: QP 26 / CRF 23.</summary>
    Speed,

    /// <summary>Сбалансированный режим: QP 22 / CRF 21.</summary>
    Balanced,

    /// <summary>Максимальное качество: QP 19 / CRF 18.</summary>
    Max,
}

/// <summary>
/// Режим tile для Real-ESRGAN. Соответствует legacy <c>tile_mode</c>
/// (<c>preset | t256 | t384 | t512</c>); <see cref="Auto"/> использует значение
/// пресета и повышает его до 384 при масштабе x3/x4.
/// </summary>
public enum TileMode
{
    /// <summary>Автоматически: tile пресета, при масштабе x3/x4 — не меньше 384.</summary>
    Auto,

    /// <summary>Фиксированный tile 256.</summary>
    T256 = 256,

    /// <summary>Фиксированный tile 384.</summary>
    T384 = 384,

    /// <summary>Фиксированный tile 512.</summary>
    T512 = 512,
}

/// <summary>
/// Пресет обработки. Соответствует legacy <c>PRESETS</c>:
/// <c>fast</c> — «Быстро», <c>balanced</c> — «Баланс», <c>max</c> — «Максимально».
/// </summary>
public enum PresetKind
{
    /// <summary>«Быстро»: x2, без интерполяции, H.264 AMF, качество Speed, tile 256.</summary>
    Fast,

    /// <summary>«Баланс»: x2, 60 FPS, HEVC AMF, качество Balanced, tile 384.</summary>
    Balanced,

    /// <summary>«Максимально»: x4, 60 FPS, HEVC AMF, качество Max, tile 512.</summary>
    Max,
}

namespace VideoBoost.Engine;

/// <summary>
/// Имена моделей Real-ESRGAN, используемые в аргументах <c>-n</c>. Значения взяты
/// из legacy <c>_resolve_model</c> и должны совпадать с папками моделей ncnn.
/// </summary>
public static class ModelNames
{
    /// <summary>Лёгкая модель по умолчанию: <c>realesr-animevideov3</c>.</summary>
    public const string Light = "realesr-animevideov3";

    /// <summary>Тяжёлая модель для обычного видео: <c>realesrgan-x4plus</c>.</summary>
    public const string Heavy = "realesrgan-x4plus";

    /// <summary>Тяжёлая модель для аниме: <c>realesrgan-x4plus-anime</c>.</summary>
    public const string HeavyAnime = "realesrgan-x4plus-anime";
}

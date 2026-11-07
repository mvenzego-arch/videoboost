namespace VideoBoost.Engine.Commands;

/// <summary>
/// Формат промежуточных кадров. Legacy <c>fmt = "jpg" if save_space else "png"</c>:
/// JPEG экономит диск, PNG сохраняет точность.
/// </summary>
public enum FrameImageFormat
{
    /// <summary>PNG без потерь (legacy: <c>save_space = false</c>).</summary>
    Png,

    /// <summary>JPEG высокого качества (legacy: <c>save_space = true</c>, <c>-qscale:v 1</c>).</summary>
    Jpeg,
}

/// <summary>
/// Расширения и шаблоны имён промежуточных кадров, перенесённые из legacy
/// <c>process_video</c> без изменений.
/// </summary>
public static class FrameImageFormats
{
    /// <summary>Шаблон имени кадров, извлечённых FFmpeg (legacy <c>%06d</c>, без префикса).</summary>
    public const string ExtractedPattern = "%06d";

    /// <summary>Шаблон имени кадров после RIFE (legacy <c>%08d</c>).</summary>
    public const string InterpolatedPattern = "%08d";

    /// <summary>Расширение файла кадра без точки: <c>png</c> или <c>jpg</c>.</summary>
    /// <param name="format">Формат кадров.</param>
    /// <returns>Строчное расширение без точки.</returns>
    public static string Extension(this FrameImageFormat format) =>
        format == FrameImageFormat.Jpeg ? "jpg" : "png";

    /// <summary>Шаблон <c>%06d.ext</c> для каталога извлечённых кадров.</summary>
    /// <param name="format">Формат кадров.</param>
    /// <returns>Шаблон имени файла для FFmpeg.</returns>
    public static string ExtractedFilePattern(this FrameImageFormat format) =>
        ExtractedPattern + "." + format.Extension();

    /// <summary>Шаблон <c>%08d.ext</c> для каталога кадров после RIFE.</summary>
    /// <param name="format">Формат кадров.</param>
    /// <returns>Шаблон имени файла для RIFE и FFmpeg.</returns>
    public static string InterpolatedFilePattern(this FrameImageFormat format) =>
        InterpolatedPattern + "." + format.Extension();

    /// <summary>
    /// Выбирает формат по флагу «экономить место»: JPEG при <see langword="true"/>,
    /// PNG при <see langword="false"/> — как в legacy.
    /// </summary>
    /// <param name="saveSpace">Пользовательский флаг экономии диска.</param>
    /// <returns>Формат промежуточных кадров.</returns>
    public static FrameImageFormat FromSaveSpace(bool saveSpace) =>
        saveSpace ? FrameImageFormat.Jpeg : FrameImageFormat.Png;
}

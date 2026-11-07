namespace VideoBoost.Engine.Commands;

/// <summary>
/// Построитель команды сборки результата. В legacy сборка и кодирование — один вызов
/// FFmpeg, поэтому строитель делегирует в <see cref="EncodeCommands.BuildEncodeCommand"/>,
/// добавляя выбор шаблона кадров <c>%06d</c>/<c>%08d</c>.
/// </summary>
public static class AssembleFrameCommands
{
    /// <summary>
    /// Выбирает шаблон имени кадров: <c>%08d.ext</c> после интерполяции RIFE,
    /// иначе <c>%06d.ext</c> — как в legacy <c>build_encode_cmd</c>.
    /// </summary>
    /// <param name="format">Формат кадров.</param>
    /// <param name="interpolated">Была ли выполнена интерполяция.</param>
    /// <returns>Шаблон имени файла для <c>-i</c>.</returns>
    public static string SelectFramePattern(FrameImageFormat format, bool interpolated) =>
        interpolated ? format.InterpolatedFilePattern() : format.ExtractedFilePattern();

    /// <summary>
    /// Строит команду сборки финальных кадров и кодирования MP4 с аудиодорожкой исходника.
    /// </summary>
    /// <param name="ffmpegPath">Путь к <c>ffmpeg.exe</c>.</param>
    /// <param name="framesDirectory">Каталог финальных кадров.</param>
    /// <param name="framePattern">Шаблон имени кадров (см. <see cref="SelectFramePattern"/>).</param>
    /// <param name="outputFps">Частота кадров результата.</param>
    /// <param name="sourceVideoPath">Исходное видео — источник аудио.</param>
    /// <param name="outputPath">Путь к MP4.</param>
    /// <param name="encoder">Кодировщик.</param>
    /// <param name="quality">Качество.</param>
    /// <param name="audioCodec">Кодек аудио из ffprobe или <see langword="null"/>.</param>
    /// <param name="progressFilePath">Файл <c>-progress</c>.</param>
    /// <returns>Команда без рабочего каталога.</returns>
    public static NativeCommand BuildAssembleCommand(
        string ffmpegPath,
        string framesDirectory,
        string framePattern,
        double outputFps,
        string sourceVideoPath,
        string outputPath,
        EncoderMode encoder,
        QualityMode quality,
        string? audioCodec,
        string progressFilePath)
    {
        var request = new EncodeCommandRequest(
            ffmpegPath,
            framesDirectory,
            framePattern,
            outputFps,
            sourceVideoPath,
            outputPath,
            progressFilePath,
            encoder,
            quality,
            audioCodec);

        return EncodeCommands.BuildEncodeCommand(request);
    }
}

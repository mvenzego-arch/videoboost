namespace VideoBoost.Engine.Commands;

/// <summary>
/// Построитель команды извлечения кадров. Полностью повторяет legacy-вызов
/// <c>process_video</c>: <c>-fps_mode passthrough</c>, шаблон <c>%06d</c>, PNG или JPEG
/// с <c>-qscale:v 1</c>.
/// </summary>
public static class ExtractFrameCommands
{
    /// <summary>
    /// Строит команду FFmpeg для разбора видео на кадры.
    /// </summary>
    /// <param name="ffmpegPath">Путь к <c>ffmpeg.exe</c>.</param>
    /// <param name="inputPath">Путь к исходному видео.</param>
    /// <param name="framesDirectory">Каталог для кадров (должен существовать к моменту запуска).</param>
    /// <param name="format">PNG или JPEG (JPEG — при «экономить место»).</param>
    /// <param name="progressFilePath">Файл <c>-progress</c> для чтения прогресса извне.</param>
    /// <returns>Команда без рабочего каталога.</returns>
    public static NativeCommand BuildExtractCommand(
        string ffmpegPath,
        string inputPath,
        string framesDirectory,
        FrameImageFormat format,
        string progressFilePath)
    {
        if (string.IsNullOrWhiteSpace(ffmpegPath))
        {
            throw new ArgumentException("Путь к ffmpeg не задан.", nameof(ffmpegPath));
        }

        if (string.IsNullOrWhiteSpace(inputPath))
        {
            throw new ArgumentException("Путь к видео не задан.", nameof(inputPath));
        }

        if (string.IsNullOrWhiteSpace(framesDirectory))
        {
            throw new ArgumentException("Каталог кадров не задан.", nameof(framesDirectory));
        }

        if (string.IsNullOrWhiteSpace(progressFilePath))
        {
            throw new ArgumentException("Файл прогресса не задан.", nameof(progressFilePath));
        }

        var arguments = new List<string>
        {
            "-y", "-hide_banner", "-nostdin",
            "-loglevel", "warning",
            "-i", inputPath,
            "-map", "0:v:0",
            "-an", "-sn", "-dn",
            "-fps_mode", "passthrough",
            "-progress", progressFilePath,
            "-nostats",
        };

        if (format == FrameImageFormat.Jpeg)
        {
            arguments.Add("-qscale:v");
            arguments.Add("1");
        }

        arguments.Add(Path.Combine(framesDirectory, format.ExtractedFilePattern()));
        return new NativeCommand(ffmpegPath, arguments);
    }
}

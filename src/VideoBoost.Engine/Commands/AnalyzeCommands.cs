namespace VideoBoost.Engine.Commands;

/// <summary>
/// Построитель команд этапа анализа: ffprobe читает длительность/fps/размеры/аудио/HDR,
/// ffmpeg отдаёт список кодировщиков для проверки доступности AMF.
/// Аргументы перенесены из legacy <c>Pipeline.probe</c> и <c>Pipeline._has_encoder</c>.
/// </summary>
public static class AnalyzeCommands
{
    /// <summary>
    /// Команда ffprobe: JSON со всеми потоками и форматом. Legacy:
    /// <c>ffprobe -v error -print_format json -show_streams -show_format &lt;path&gt;</c>.
    /// </summary>
    /// <param name="ffprobePath">Путь к <c>ffprobe.exe</c>.</param>
    /// <param name="inputPath">Путь к исходному видео (кириллица и пробелы допустимы).</param>
    /// <returns>Команда без рабочего каталога.</returns>
    public static NativeCommand BuildProbeCommand(string ffprobePath, string inputPath)
    {
        if (string.IsNullOrWhiteSpace(ffprobePath))
        {
            throw new ArgumentException("Путь к ffprobe не задан.", nameof(ffprobePath));
        }

        if (string.IsNullOrWhiteSpace(inputPath))
        {
            throw new ArgumentException("Путь к видео не задан.", nameof(inputPath));
        }

        var arguments = new List<string>
        {
            "-v", "error",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            inputPath,
        };

        return new NativeCommand(ffprobePath, arguments);
    }

    /// <summary>
    /// Команда перечисления кодировщиков FFmpeg (legacy <c>-hide_banner -encoders</c>).
    /// По её stdout пайплайн решает, доступен ли <c>hevc_amf</c>/<c>h264_amf</c>.
    /// </summary>
    /// <param name="ffmpegPath">Путь к <c>ffmpeg.exe</c>.</param>
    /// <returns>Команда без рабочего каталога.</returns>
    public static NativeCommand BuildEncoderListCommand(string ffmpegPath)
    {
        if (string.IsNullOrWhiteSpace(ffmpegPath))
        {
            throw new ArgumentException("Путь к ffmpeg не задан.", nameof(ffmpegPath));
        }

        return new NativeCommand(ffmpegPath, new List<string> { "-hide_banner", "-encoders" });
    }
}

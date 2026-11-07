namespace VideoBoost.Engine.Commands;

/// <summary>
/// Параметры команды сборки/кодирования: кадры + исходник (для аудиодорожки).
/// Соответствует единому legacy-вызову FFmpeg из шага 4 <c>process_video</c>.
/// </summary>
/// <param name="FfmpegPath">Путь к <c>ffmpeg.exe</c>.</param>
/// <param name="FramesDirectory">Каталог финальных кадров.</param>
/// <param name="FramePattern">Шаблон имени кадров: <c>%06d.ext</c> или <c>%08d.ext</c>.</param>
/// <param name="OutputFps">Частота кадров результата (в legacy — 6 знаков после точки).</param>
/// <param name="SourceVideoPath">Исходное видео — источник аудиодорожки.</param>
/// <param name="OutputPath">Путь к собираемому MP4.</param>
/// <param name="ProgressFilePath">Файл <c>-progress</c> для чтения прогресса извне.</param>
/// <param name="Encoder">Кодировщик; <see cref="EncoderMode.Auto"/> трактуется как HEVC AMF (legacy-фолбэк).</param>
/// <param name="Quality">Качество; <see cref="QualityMode.Auto"/> трактуется как Balanced.</param>
/// <param name="AudioCodec">
/// Кодек аудио из ffprobe: <c>aac/mp3/ac3/eac3/alac</c> копируются, остальные
/// перекодируются в AAC 192k, <see langword="null"/> — дорожки нет (<c>-an</c>).
/// </param>
public sealed record EncodeCommandRequest(
    string FfmpegPath,
    string FramesDirectory,
    string FramePattern,
    double OutputFps,
    string SourceVideoPath,
    string OutputPath,
    string ProgressFilePath,
    EncoderMode Encoder,
    QualityMode Quality = QualityMode.Balanced,
    string? AudioCodec = null);

/// <summary>
/// Построитель команды кодирования FFmpeg: AMD AMF (<c>h264_amf</c>/<c>hevc_amf</c>)
/// с QP из <see cref="QualityLevels"/> либо <c>libx264</c> с CRF, звук copy/AAC,
/// <c>-pix_fmt yuv420p</c> и <c>-movflags +faststart</c> — по legacy.
/// </summary>
public static class EncodeCommands
{
    private static readonly HashSet<string> SafeAudioCopyCodecs =
        new(StringComparer.OrdinalIgnoreCase) { "aac", "mp3", "ac3", "eac3", "alac" };

    /// <summary>
    /// Строит полную команду сборки кадров и кодирования результата.
    /// </summary>
    /// <param name="request">Параметры команды.</param>
    /// <returns>Команда без рабочего каталога.</returns>
    public static NativeCommand BuildEncodeCommand(EncodeCommandRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (string.IsNullOrWhiteSpace(request.FfmpegPath))
        {
            throw new ArgumentException("Путь к ffmpeg не задан.", nameof(request));
        }

        if (string.IsNullOrWhiteSpace(request.FramesDirectory))
        {
            throw new ArgumentException("Каталог кадров не задан.", nameof(request));
        }

        if (string.IsNullOrWhiteSpace(request.FramePattern))
        {
            throw new ArgumentException("Шаблон кадров не задан.", nameof(request));
        }

        if (request.OutputFps <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(request), request.OutputFps, "FPS должен быть положительным.");
        }

        if (string.IsNullOrWhiteSpace(request.SourceVideoPath))
        {
            throw new ArgumentException("Путь к исходному видео не задан.", nameof(request));
        }

        if (string.IsNullOrWhiteSpace(request.OutputPath))
        {
            throw new ArgumentException("Путь к результату не задан.", nameof(request));
        }

        if (string.IsNullOrWhiteSpace(request.ProgressFilePath))
        {
            throw new ArgumentException("Файл прогресса не задан.", nameof(request));
        }

        var arguments = new List<string>
        {
            "-y", "-hide_banner", "-nostdin",
            "-loglevel", "warning",
            "-framerate", CommandBuild.Invariant(request.OutputFps, "0.000000"),
            "-start_number", "1",
            "-i", Path.Combine(request.FramesDirectory, request.FramePattern),
            "-i", request.SourceVideoPath,
            "-map", "0:v:0",
            "-map", "1:a:0?",
        };

        arguments.AddRange(BuildVideoCodecArguments(request.Encoder, request.Quality));
        arguments.AddRange(new[] { "-pix_fmt", "yuv420p" });
        arguments.AddRange(BuildAudioArguments(request.AudioCodec));
        arguments.AddRange(new[]
        {
            "-movflags", "+faststart",
            "-progress", request.ProgressFilePath,
            "-nostats",
            request.OutputPath,
        });

        return new NativeCommand(request.FfmpegPath, arguments);
    }

    /// <summary>
    /// Аргументы видеокодера: AMF — <c>-c:v &lt;codec&gt; -quality &lt;key&gt; -rc cqp
    /// -qp_i/-qp_p &lt;qp&gt;</c> (+<c>-tag:v hvc1</c> для HEVC); CPU — <c>libx264
    /// -preset fast -crf &lt;crf&gt;</c>.
    /// </summary>
    /// <param name="encoder">Кодировщик.</param>
    /// <param name="quality">Качество.</param>
    /// <returns>Список аргументов в legacy-порядке.</returns>
    public static IReadOnlyList<string> BuildVideoCodecArguments(EncoderMode encoder, QualityMode quality)
    {
        var arguments = new List<string>();
        var encoderName = GetEncoderName(encoder);

        if (encoder == EncoderMode.Cpu)
        {
            var (_, crf) = QualityLevels.For(quality);
            arguments.AddRange(new[]
            {
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", CommandBuild.Invariant(crf),
            });
            return arguments;
        }

        var (qp, _) = QualityLevels.For(quality);
        arguments.AddRange(new[]
        {
            "-c:v", encoderName,
            "-quality", GetQualityKey(quality),
            "-rc", "cqp",
            "-qp_i", CommandBuild.Invariant(qp),
            "-qp_p", CommandBuild.Invariant(qp),
        });

        if (encoderName.Contains("hevc", StringComparison.Ordinal))
        {
            arguments.AddRange(new[] { "-tag:v", "hvc1" });
        }

        return arguments;
    }

    /// <summary>
    /// Аргументы аудио по legacy: безопасные кодеки — <c>-c:a copy</c>, остальные —
    /// <c>-c:a aac -b:a 192k</c>, отсутствие дорожки — <c>-an</c>.
    /// </summary>
    /// <param name="audioCodec">Кодек из ffprobe или <see langword="null"/>.</param>
    /// <returns>Список аргументов аудио.</returns>
    public static IReadOnlyList<string> BuildAudioArguments(string? audioCodec)
    {
        if (string.IsNullOrWhiteSpace(audioCodec))
        {
            return new List<string> { "-an" };
        }

        if (SafeAudioCopyCodecs.Contains(audioCodec))
        {
            return new List<string> { "-c:a", "copy" };
        }

        return new List<string> { "-c:a", "aac", "-b:a", "192k" };
    }

    /// <summary>
    /// Имя кодировщика FFmpeg. <see cref="EncoderMode.Auto"/> и неизвестные значения
    /// дают <c>hevc_amf</c> — legacy-фолбэк <c>_resolve_encoder</c>.
    /// </summary>
    /// <param name="encoder">Режим кодировщика.</param>
    /// <returns><c>h264_amf</c>, <c>hevc_amf</c> или <c>libx264</c>.</returns>
    public static string GetEncoderName(EncoderMode encoder) => encoder switch
    {
        EncoderMode.AmfH264 => "h264_amf",
        EncoderMode.Cpu => "libx264",
        _ => "hevc_amf",
    };

    /// <summary>
    /// Ключ качества для AMF <c>-quality</c>: <c>speed</c>/<c>balanced</c>/<c>quality</c>
    /// (legacy-значения; <see cref="QualityMode.Max"/> — это <c>quality</c>).
    /// </summary>
    /// <param name="quality">Режим качества.</param>
    /// <returns>Строка legacy-ключа качества.</returns>
    public static string GetQualityKey(QualityMode quality) => quality switch
    {
        QualityMode.Speed => "speed",
        QualityMode.Max => "quality",
        _ => "balanced",
    };
}

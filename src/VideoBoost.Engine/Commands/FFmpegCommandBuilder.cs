using System.Globalization;

namespace VideoBoost.Engine.Commands;

/// <summary>Сборка аргументов FFmpeg. Флаги перенесены 1:1 из legacy engine.py (ветка legacy-python).</summary>
public static class FFmpegCommandBuilder
{
    private static readonly HashSet<string> SafeAudio = new(StringComparer.OrdinalIgnoreCase)
    {
        "aac", "mp3", "ac3", "eac3", "alac",
    };

    /// <summary>Проверка наличия аппаратных кодировщиков: текст вывода разбирается runtime-ом.</summary>
    public static IReadOnlyList<string> ListEncoders(ToolPaths tools) =>
        [tools.FFmpeg, "-hide_banner", "-encoders"];

    /// <summary>Шаг 1/4: извлечение кадров (-fps_mode passthrough; JPG = qscale 1).</summary>
    public static IReadOnlyList<string> ExtractFrames(
        ToolPaths tools, string videoPath, string framesDir, FrameFormat format, string progressFile)
    {
        var cmd = new List<string>
        {
            tools.FFmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "warning",
            "-i", videoPath,
            "-map", "0:v:0", "-an", "-sn", "-dn",
            "-fps_mode", "passthrough",
            "-progress", progressFile, "-nostats",
        };
        if (format == FrameFormat.Jpg)
        {
            cmd.Add("-qscale:v");
            cmd.Add("1");
        }
        cmd.Add(Path.Combine(framesDir, $"%06d.{EngineFormats.Ext(format)}"));
        return cmd;
    }

    /// <summary>Звук: дорожка с совместимым кодеком копируется; экзотика — AAC 192k; нет дорожки — -an.</summary>
    public static IReadOnlyList<string> AudioArgs(string? audioCodec)
    {
        if (string.IsNullOrWhiteSpace(audioCodec))
        {
            return ["-an"];
        }
        if (SafeAudio.Contains(audioCodec))
        {
            return ["-c:a", "copy"];
        }
        return ["-c:a", "aac", "-b:a", "192k"];
    }

    /// <summary>Шаг 4/4: кодирование кадров в MP4. AMF (GPU) или libx264 (CPU fallback).</summary>
    public static IReadOnlyList<string> EncodeFrames(EncodePlan plan)
    {
        var fps = plan.OutFps.ToString("F6", CultureInfo.InvariantCulture);
        var pattern = $"%0{(plan.Interpolated ? 8 : 6)}d.{EngineFormats.Ext(plan.FrameFormat)}";
        var cmd = new List<string>
        {
            plan.Tools.FFmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "warning",
            "-framerate", fps, "-start_number", "1",
            "-i", Path.Combine(plan.FramesDir, pattern),
            "-i", plan.VideoPath,
            "-map", "0:v:0", "-map", "1:a:0?",
        };

        if (plan.UseAmf && plan.Encoder is not EncoderKind.Cpu)
        {
            var codec = plan.Encoder == EncoderKind.AmfHevc ? "hevc_amf" : "h264_amf";
            cmd.Add("-c:v");
            cmd.Add(codec);
            cmd.Add("-quality");
            cmd.Add(QualityKey(plan.Quality));
            cmd.Add("-rc");
            cmd.Add("cqp");
            cmd.Add("-qp_i");
            cmd.Add(plan.Qp.ToString(CultureInfo.InvariantCulture));
            cmd.Add("-qp_p");
            cmd.Add(plan.Qp.ToString(CultureInfo.InvariantCulture));
            if (plan.Encoder == EncoderKind.AmfHevc)
            {
                cmd.Add("-tag:v");
                cmd.Add("hvc1");
            }
        }
        else
        {
            cmd.Add("-c:v");
            cmd.Add("libx264");
            cmd.Add("-preset");
            cmd.Add("fast");
            cmd.Add("-crf");
            cmd.Add(plan.Crf.ToString(CultureInfo.InvariantCulture));
        }

        cmd.Add("-pix_fmt");
        cmd.Add("yuv420p");
        cmd.AddRange(AudioArgs(plan.AudioCodec));
        cmd.Add("-movflags");
        cmd.Add("+faststart");
        cmd.Add("-progress");
        cmd.Add(plan.ProgressFile);
        cmd.Add("-nostats");
        cmd.Add(plan.PartPath);
        return cmd;
    }

    /// <summary>Строковое имя уровня качества для флага -quality (AMF).</summary>
    public static string QualityKey(QualityKind kind) => kind switch
    {
        QualityKind.Speed => "speed",
        QualityKind.Quality => "quality",
        _ => "balanced",
    };
}

/// <summary>Параметры шага кодирования (шаг 4/4).</summary>
public sealed record EncodePlan(
    ToolPaths Tools,
    string VideoPath,
    string FramesDir,
    FrameFormat FrameFormat,
    bool Interpolated,
    double OutFps,
    EncoderKind Encoder,
    bool UseAmf,
    QualityKind Quality,
    int Qp,
    int Crf,
    string? AudioCodec,
    string ProgressFile,
    string PartPath);

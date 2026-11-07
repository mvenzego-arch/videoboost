namespace VideoBoost.Engine;

/// <summary>Один шаг плана: команда, её аргументы и (для ncnn-инструментов) рабочая папка exe.</summary>
public sealed record EngineStep(string Title, IReadOnlyList<string> Arguments, string? WorkingDirectory = null);

/// <summary>Полный план обработки видео: извлечение → апскейл → интерполяция → кодирование.</summary>
public sealed record EnginePlan(IReadOnlyList<EngineStep> Steps);

/// <summary>Рабочие пути одного прогона (temp\ и выход).</summary>
public sealed record EnginePaths(
    string FramesDir,
    string UpscaledDir,
    string SmoothDir,
    string ProgressFile,
    string PartPath);

/// <summary>Настройки прогона; null/пустые значения берутся из пресета.</summary>
public sealed record PlanOptions(
    FrameFormat FrameFormat = FrameFormat.Jpg,
    ScaleMode Scale = ScaleMode.Preset,
    int VideoHeight = 0,
    TileMode TileMode = TileMode.Preset,
    EncoderKind? Encoder = null,
    QualityKind? Quality = null,
    ContentKind Content = ContentKind.General,
    ModelMode Model = ModelMode.Auto,
    int TargetFrames = 0,
    double OutFps = 60.0,
    bool UseAmf = true,
    string? AudioCodec = null);

/// <summary>
/// Планировщик пайплайна: строит последовательность шагов с готовыми аргументами.
/// Исполнение процессов (запуск, отмена, прогресс) — следующий слой, engine-dev.
/// </summary>
public static class EnginePlanBuilder
{
    public static EnginePlan Build(ToolPaths tools, string videoPath, EnginePaths paths, Preset preset, PlanOptions options)
    {
        var scale = ScaleSelection.Resolve(options.Scale, preset, options.VideoHeight);
        var fmt = options.FrameFormat;

        var steps = new List<EngineStep>
        {
            new(
                "Извлечение кадров",
                Commands.FFmpegCommandBuilder.ExtractFrames(tools, videoPath, paths.FramesDir, fmt, paths.ProgressFile)),
        };

        var upscaled = scale >= 2;
        if (upscaled)
        {
            var model = Commands.EsrganCommandBuilder.ResolveModel(options.Model, options.Content, scale, preset);
            var tile = TileSelection.Resolve(options.TileMode, preset, scale);
            steps.Add(new(
                "Нейросетевой апскейл",
                Commands.EsrganCommandBuilder.Upscale(new(
                    tools, paths.FramesDir, paths.UpscaledDir, scale, model, tile, fmt)),
                WorkingDirectory: ParentOf(tools.Realesrgan)));
        }

        var interpolated = options.TargetFrames > 0;
        if (interpolated)
        {
            var inputDir = upscaled ? paths.UpscaledDir : paths.FramesDir;
            steps.Add(new(
                "Интерполяция кадров",
                Commands.RifeCommandBuilder.Interpolate(new(
                    tools, inputDir, paths.SmoothDir, options.TargetFrames, fmt, UltraHd: false)),
                WorkingDirectory: ParentOf(tools.Rife)));
        }

        var encoder = options.Encoder ?? preset.Encoder;
        var quality = options.Quality ?? preset.Quality;
        var (qp, crf) = Presets.QualityLevels(quality);
        var framesIn = interpolated
            ? paths.SmoothDir
            : upscaled ? paths.UpscaledDir : paths.FramesDir;

        steps.Add(new(
            "Кодирование",
            Commands.FFmpegCommandBuilder.EncodeFrames(new(
                tools, videoPath, framesIn, fmt,
                Interpolated: interpolated,
                OutFps: options.OutFps,
                Encoder: encoder,
                UseAmf: options.UseAmf && encoder is not EncoderKind.Cpu,
                Quality: quality, Qp: qp, Crf: crf,
                AudioCodec: options.AudioCodec,
                ProgressFile: paths.ProgressFile,
                PartPath: paths.PartPath))));

        return new(steps);
    }

    private static string ParentOf(string exePath) => Path.GetDirectoryName(exePath) ?? string.Empty;
}

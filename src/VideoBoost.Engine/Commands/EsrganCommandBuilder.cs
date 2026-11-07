using System.Globalization;
using VideoBoost.Engine;

namespace VideoBoost.Engine.Commands;

/// <summary>Сборка аргументов Real-ESRGAN (ncnn Vulcan, tile по VRAM).</summary>
public static class EsrganCommandBuilder
{
    /// <summary>Шаг 2/4: апскейл кадров (worker: cwd = папка exe — там models).</summary>
    public static IReadOnlyList<string> Upscale(UpscalePlan plan) => new List<string>
    {
        plan.Tools.Realesrgan,
        "-i", plan.FramesDir, "-o", plan.OutputDir,
        "-s", plan.Scale.ToString(CultureInfo.InvariantCulture),
        "-n", plan.Model,
        "-m", plan.Tools.RealesrganModelsDir,
        "-t", plan.Tile.ToString(CultureInfo.InvariantCulture),
        "-g", "0",
        "-j", "1:1:1",
        "-f", EngineFormats.Ext(plan.FrameFormat),
    };

    /// <summary>Модель по типу видео; тяжёлая умеет только x4 — иначе лёгкая (legacy _resolve_model).</summary>
    public static string ResolveModel(ModelMode mode, ContentKind content, int scale, Preset preset)
    {
        var heavy = (mode == ModelMode.Heavy) || (mode == ModelMode.Auto && preset.Key == "max");
        if (scale < 4 && heavy)
        {
            heavy = false;
        }
        if (heavy)
        {
            return content == ContentKind.Anime ? "realesrgan-x4plus-anime" : "realesrgan-x4plus";
        }
        return "realesr-animevideov3";
    }
}

/// <summary>Параметры шага апскейла (шаг 2/4).</summary>
public sealed record UpscalePlan(
    ToolPaths Tools,
    string FramesDir,
    string OutputDir,
    int Scale,
    string Model,
    int Tile,
    FrameFormat FrameFormat);

using Xunit;
using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>План пайплайна: последовательность шагов, tile, входные папки кодирования.</summary>
public class EnginePlanTests
{
    private static readonly ToolPaths Tools = new(
        FFmpeg: @"C:\tools\ffmpeg.exe",
        FFprobe: @"C:\tools\ffprobe.exe",
        Realesrgan: @"C:\tools\realesrgan\realesrgan-ncnn-vulkan.exe",
        RealesrganModelsDir: @"C:\tools\realesrgan\models",
        Rife: @"C:\tools\rife\rife-ncnn-vulkan.exe",
        RifeModel: @"C:\tools\rife\models\rife-v4.6");

    private static readonly EnginePaths Paths = new(
        FramesDir: @"T:\frames",
        UpscaledDir: @"T:\upscaled",
        SmoothDir: @"T:\smooth",
        ProgressFile: @"T:\progress.txt",
        PartPath: @"T:\out\result.part.mp4");

    private const string Video = @"E:\Проверка папки\тест.mp4";

    private static int Idx(IReadOnlyList<string> args, string token)
    {
        for (var i = 0; i < args.Count; i++)
        {
            if (args[i] == token)
            {
                return i;
            }
        }
        return -1;
    }

    [Fact]
    public void FastPreset_ProducesThreeSteps()
    {
        var plan = EnginePlanBuilder.Build(Tools, Video, Paths, Presets.Fast, new PlanOptions());

        Assert.Equal(3, plan.Steps.Count);
        Assert.Equal(
            new[] { "Извлечение кадров", "Нейросетевой апскейл", "Кодирование" },
            plan.Steps.Select(static s => s.Title).ToArray());
        Assert.Equal(Path.GetDirectoryName(Tools.Realesrgan), plan.Steps[1].WorkingDirectory);
        Assert.Equal(Paths.PartPath, plan.Steps[2].Arguments[^1]);
    }

    [Fact]
    public void BalancedWithInterpolation_ProducesFourSteps()
    {
        var plan = EnginePlanBuilder.Build(Tools, Video, Paths, Presets.Balanced, new PlanOptions { TargetFrames = 90 });

        Assert.Equal(4, plan.Steps.Count);
        var interp = plan.Steps.First(static s => s.Title == "Интерполяция кадров");
        Assert.Equal(Path.GetDirectoryName(Tools.Rife), interp.WorkingDirectory);
        Assert.Equal("90", interp.Arguments[Idx(interp.Arguments, "-n") + 1]);

        var encode = plan.Steps.First(static s => s.Title == "Кодирование");
        Assert.Equal(Path.Combine(Paths.SmoothDir, "%08d.jpg"), encode.Arguments[Idx(encode.Arguments, "-i") + 1]);
    }

    [Fact]
    public void FastPreset_TileAndModelPassThrough()
    {
        var plan = EnginePlanBuilder.Build(Tools, Video, Paths, Presets.Fast, new PlanOptions());

        var upscale = plan.Steps.First(static s => s.Title == "Нейросетевой апскейл");
        Assert.Equal("256", upscale.Arguments[Idx(upscale.Arguments, "-t") + 1]);
        Assert.Equal("realesr-animevideov3", upscale.Arguments[Idx(upscale.Arguments, "-n") + 1]);
    }

    [Fact]
    public void WithoutUpscale_EncodeReadsFramesDir()
    {
        var options = new PlanOptions { Scale = ScaleMode.X1 };
        var plan = EnginePlanBuilder.Build(Tools, Video, Paths, Presets.Fast, options);

        Assert.Equal(2, plan.Steps.Count);
        var encode = plan.Steps.First(static s => s.Title == "Кодирование");
        Assert.Equal(Path.Combine(Paths.FramesDir, "%06d.jpg"), encode.Arguments[Idx(encode.Arguments, "-i") + 1]);
    }
}

using System.Globalization;
using VideoBoost.Engine;

namespace VideoBoost.Engine.Commands;

/// <summary>Сборка аргументов RIFE (ncnn Vulcan, интерполяция кадров).</summary>
public static class RifeCommandBuilder
{
    /// <summary>Шаг 3/4: интерполяция до TargetFrames (cwd = папка exe RIFE); -u — UHD-режим при нехватке VRAM.</summary>
    public static IReadOnlyList<string> Interpolate(InterpolatePlan plan)
    {
        var cmd = new List<string>
        {
            plan.Tools.Rife,
            "-i", plan.InputDir, "-o", plan.OutputDir,
            "-n", plan.TargetFrames.ToString(CultureInfo.InvariantCulture),
            "-m", plan.Tools.RifeModel,
            "-g", "0",
            "-j", "1:1:1",
            "-f", $"%08d.{EngineFormats.Ext(plan.FrameFormat)}",
        };
        if (plan.UltraHd)
        {
            cmd.Add("-u");
        }
        return cmd;
    }
}

/// <summary>Параметры шага интерполяции (шаг 3/4).</summary>
public sealed record InterpolatePlan(
    ToolPaths Tools,
    string InputDir,
    string OutputDir,
    int TargetFrames,
    FrameFormat FrameFormat,
    bool UltraHd);

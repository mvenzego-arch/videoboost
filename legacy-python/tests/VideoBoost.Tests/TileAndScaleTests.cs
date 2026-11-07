using Xunit;
using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>Масштаб и tile — логика legacy _resolve_scale/_resolve_tile.</summary>
public class TileAndScaleTests
{
    private static readonly Preset Fast = Presets.Fast;

    [Theory]
    [InlineData((int)ScaleMode.X2, 2)]
    [InlineData((int)ScaleMode.X3, 3)]
    [InlineData((int)ScaleMode.X4, 4)]
    public void FixedScaleModes_ReturnTheirNumber(int mode, int expected)
    {
        Assert.Equal(expected, ScaleSelection.Resolve((ScaleMode)mode, Fast, videoHeight: 1080));
    }

    [Fact]
    public void Auto4320_At1080p_ScalesByFour()
    {
        Assert.Equal(4, ScaleSelection.Resolve(ScaleMode.Auto4320, Fast, 1080));
    }

    [Fact]
    public void Auto2160_At1080p_ScalesByTwo()
    {
        Assert.Equal(2, ScaleSelection.Resolve(ScaleMode.Auto2160, Fast, 1080));
    }

    [Fact]
    public void Auto_AboveTarget_SkipsUpscale()
    {
        Assert.Equal(1, ScaleSelection.Resolve(ScaleMode.Auto2160, Fast, 2160));
        Assert.Equal(1, ScaleSelection.Resolve(ScaleMode.Auto4320, Fast, 4320));
    }

    [Fact]
    public void Auto_WithoutHeight_FallsBackToPreset()
    {
        Assert.Equal(2, ScaleSelection.Resolve(ScaleMode.Auto4320, Fast, 0));
    }

    [Fact]
    public void Tile_PresetMode_AppliesLiftOnScale3Plus()
    {
        Assert.Equal(256, TileSelection.Resolve(TileMode.Preset, Fast, scale: 2));
        Assert.Equal(384, TileSelection.Resolve(TileMode.Preset, Fast, scale: 4));
    }

    [Fact]
    public void Tile_FixedModes_BypassLift()
    {
        var small = new Preset("synth", "Synthetic", 1, false, 60, EncoderKind.AmfH264, QualityKind.Speed, 256, "");
        Assert.Equal(512, TileSelection.Resolve(TileMode.Fixed512, small, scale: 4));
    }

    [Fact]
    public void Tile_ClampsToLegacyBounds()
    {
        var tiny = new Preset("synth", "Synthetic", 1, false, 60, EncoderKind.AmfH264, QualityKind.Speed, 100, "");
        var huge = new Preset("synth", "Synthetic", 1, false, 60, EncoderKind.AmfH264, QualityKind.Speed, 999, "");
        Assert.Equal(128, TileSelection.Resolve(TileMode.Preset, tiny, scale: 1));
        Assert.Equal(640, TileSelection.Resolve(TileMode.Preset, huge, scale: 1));
    }
}

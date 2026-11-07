using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>Контрактные проверки публичных enum-ов движка.</summary>
public sealed class EngineEnumsTests
{
    [Fact]
    public void FpsMode_HasExactlyTwoValues_WithLegacyTargets()
    {
        var values = Enum.GetValues<FpsMode>();

        Assert.Equal(2, values.Length);
        Assert.Equal(new[] { FpsMode.Fps60, FpsMode.Fps120 }, values);
        Assert.Equal(60, (int)FpsMode.Fps60);
        Assert.Equal(120, (int)FpsMode.Fps120);
    }

    [Fact]
    public void Enums_HaveExpectedMembers()
    {
        Assert.Equal(
            new[]
            {
                ScaleMode.X2,
                ScaleMode.X3,
                ScaleMode.X4,
                ScaleMode.Auto2160,
                ScaleMode.Auto4320,
            },
            Enum.GetValues<ScaleMode>());

        Assert.Equal(
            new[] { ModelMode.Auto, ModelMode.Light, ModelMode.Heavy },
            Enum.GetValues<ModelMode>());

        Assert.Equal(
            new[] { EncoderMode.Auto, EncoderMode.AmfH264, EncoderMode.AmfHevc, EncoderMode.Cpu },
            Enum.GetValues<EncoderMode>());

        Assert.Equal(
            new[] { QualityMode.Auto, QualityMode.Speed, QualityMode.Balanced, QualityMode.Max },
            Enum.GetValues<QualityMode>());

        Assert.Equal(
            new[] { TileMode.Auto, TileMode.T256, TileMode.T384, TileMode.T512 },
            Enum.GetValues<TileMode>());

        Assert.Equal(
            new[] { PresetKind.Fast, PresetKind.Balanced, PresetKind.Max },
            Enum.GetValues<PresetKind>());

        Assert.Equal(256, (int)TileMode.T256);
        Assert.Equal(384, (int)TileMode.T384);
        Assert.Equal(512, (int)TileMode.T512);
    }
}

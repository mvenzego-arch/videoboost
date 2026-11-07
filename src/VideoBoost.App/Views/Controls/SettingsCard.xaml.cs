using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using VideoBoost.Engine;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Правая карточка настроек: пресеты + 8 строк, всегда видимых (дельта v3.1).
/// Все значения — из <see cref="PresetDefaults"/> движка.
/// </summary>
public sealed partial class SettingsCard : UserControl
{
    private bool _applyingPreset;

    /// <summary>Создаёт карточку настроек и заполняет пилюли значениями по умолчанию (пресет «Баланс»).</summary>
    public SettingsCard()
    {
        InitializeComponent();

        PresetPills.Items =
        [
            new PillItem("Быстро", "x2 · до 4K"),
            new PillItem("Баланс", "x2 · до 4K · 60 FPS"),
            new PillItem("Максимально", "x4 · до 8K · 60 FPS"),
        ];
        ScalePills.Items =
        [
            new PillItem("x2"),
            new PillItem("x3"),
            new PillItem("x4"),
            new PillItem("4K авто"),
            new PillItem("8K авто"),
        ];
        ModelPills.Items =
        [
            new PillItem("Авто"),
            new PillItem("Лёгкая"),
            new PillItem("Тяжёлая"),
        ];
        FpsPills.Items =
        [
            new PillItem("60 FPS"),
            new PillItem("120 FPS"),
        ];
        ContentPills.Items =
        [
            new PillItem("Обычное"),
            new PillItem("Аниме"),
        ];
        EncoderPills.Items =
        [
            new PillItem("Авто"),
            new PillItem("H.264"),
            new PillItem("H.265"),
            new PillItem("CPU"),
        ];
        QualityPills.Items =
        [
            new PillItem("Авто"),
            new PillItem("Скорость"),
            new PillItem("Баланс"),
            new PillItem("Макс"),
        ];
        TilePills.Items =
        [
            new PillItem("Авто"),
            new PillItem("256"),
            new PillItem("384"),
            new PillItem("512"),
        ];

        // Дефолты legacy: пресет «Баланс», масштаб x2, модель авто, 60 FPS, всё остальное — «Авто».
        PresetPills.SelectedIndex = (int)PresetKind.Balanced;
        ScalePills.SelectedIndex = 0;
        ModelPills.SelectedIndex = 0;
        FpsPills.SelectedIndex = 0;
        ContentPills.SelectedIndex = 0;
        EncoderPills.SelectedIndex = 0;
        QualityPills.SelectedIndex = 0;
        TilePills.SelectedIndex = 0;
        InterpSwitch.IsOn = PresetDefaults.Balanced.Interpolate;
        SaveSpaceSwitch.IsOn = PresetDefaults.Balanced.SaveSpace;
        PresetDescriptionText.Text = PresetDefaults.Balanced.Description;

        PresetPills.SelectedIndexChanged += PresetPills_SelectedIndexChanged;
    }

    /// <summary>Якорь для TeachingTip8K (предупреждение о x4/8K).</summary>
    public PillChoice PresetPillsAnchor => PresetPills;

    private void SettingsCard_Loaded(object sender, RoutedEventArgs e)
    {
        // Segmented сбрасывает SelectedIndex при применении шаблона — восстанавливаем один раз.
        if (PresetPills.SelectedIndex < 0)
        {
            PresetPills.SelectedIndex = (int)PresetKind.Balanced;
        }

        ScalePills.SelectedIndex = ScalePills.SelectedIndex < 0 ? 0 : ScalePills.SelectedIndex;
        ModelPills.SelectedIndex = ModelPills.SelectedIndex < 0 ? 0 : ModelPills.SelectedIndex;
        FpsPills.SelectedIndex = FpsPills.SelectedIndex < 0 ? 0 : FpsPills.SelectedIndex;
        ContentPills.SelectedIndex = ContentPills.SelectedIndex < 0 ? 0 : ContentPills.SelectedIndex;
        EncoderPills.SelectedIndex = EncoderPills.SelectedIndex < 0 ? 0 : EncoderPills.SelectedIndex;
        QualityPills.SelectedIndex = QualityPills.SelectedIndex < 0 ? 0 : QualityPills.SelectedIndex;
        TilePills.SelectedIndex = TilePills.SelectedIndex < 0 ? 0 : TilePills.SelectedIndex;
    }

    private void PresetPills_SelectedIndexChanged(object? sender, int index)
    {
        if (_applyingPreset || index < 0 || index >= PresetDefaults.All.Count)
        {
            return;
        }

        ApplyPreset((PresetKind)index);
    }

    /// <summary>
    /// Пересев дочерних пилюль по пресету — паритет legacy <c>_on_preset_changed</c>.
    /// </summary>
    private void ApplyPreset(PresetKind kind)
    {
        _applyingPreset = true;
        try
        {
            PresetDefinition preset = PresetDefaults.For(kind);
            PresetDescriptionText.Text = preset.Description;

            ScalePills.SelectedIndex = preset.Scale switch
            {
                ScaleMode.X2 => 0,
                ScaleMode.X3 => 1,
                ScaleMode.X4 => 2,
                ScaleMode.Auto2160 => 3,
                ScaleMode.Auto4320 => 4,
                _ => 0,
            };
            ModelPills.SelectedIndex = 0;
            FpsPills.SelectedIndex = preset.Fps == FpsMode.Fps120 ? 1 : 0;
            EncoderPills.SelectedIndex = 0;
            QualityPills.SelectedIndex = 0;
            TilePills.SelectedIndex = 0;
            InterpSwitch.IsOn = preset.Interpolate;
        }
        finally
        {
            _applyingPreset = false;
        }
    }
}

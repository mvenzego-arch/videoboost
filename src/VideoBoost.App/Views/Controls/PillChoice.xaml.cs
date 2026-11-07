using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Единая обёртка над <see cref="CommunityToolkit.WinUI.Controls.Segmented"/>:
/// чипы 32 px и пресеты 48 px с подписью. Все 8 групп выбора используют только её.
/// </summary>
public sealed partial class PillChoice : UserControl
{
    /// <summary>Элементы выбора (заголовок + необязательная подпись).</summary>
    public static readonly DependencyProperty ItemsProperty = DependencyProperty.Register(
        nameof(Items),
        typeof(IList<PillItem>),
        typeof(PillChoice),
        new PropertyMetadata(null));

    /// <summary>Индекс выбранной пилюли; -1 — ничего не выбрано.</summary>
    public static readonly DependencyProperty SelectedIndexProperty = DependencyProperty.Register(
        nameof(SelectedIndex),
        typeof(int),
        typeof(PillChoice),
        new PropertyMetadata(-1));

    /// <summary>Растягивать группу на всю ширину (нужно трём пресетам).</summary>
    public static readonly DependencyProperty StretchProperty = DependencyProperty.Register(
        nameof(Stretch),
        typeof(bool),
        typeof(PillChoice),
        new PropertyMetadata(false, OnStretchChanged));

    /// <summary>Создаёт обёртку.</summary>
    public PillChoice()
    {
        InitializeComponent();
    }

    /// <summary>Срабатывает после смены выбора; аргумент — новый индекс.</summary>
    public event EventHandler<int>? SelectedIndexChanged;

    /// <summary>Элементы выбора.</summary>
    public IList<PillItem>? Items
    {
        get => (IList<PillItem>?)GetValue(ItemsProperty);
        set => SetValue(ItemsProperty, value);
    }

    /// <summary>Индекс выбранной пилюли.</summary>
    public int SelectedIndex
    {
        get => (int)GetValue(SelectedIndexProperty);
        set => SetValue(SelectedIndexProperty, value);
    }

    /// <summary>Растягивать группу по ширине контейнера.</summary>
    public bool Stretch
    {
        get => (bool)GetValue(StretchProperty);
        set => SetValue(StretchProperty, value);
    }

    private static void OnStretchChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        PillChoice choice = (PillChoice)d;
        if (choice.SegmentedHost is not null)
        {
            choice.SegmentedHost.HorizontalAlignment =
                (bool)e.NewValue ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private void SegmentedHost_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        SelectedIndexChanged?.Invoke(this, SelectedIndex);
    }
}

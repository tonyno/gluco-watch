using System;
using System.Drawing;
using System.Drawing.Text;
using System.Windows.Forms;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Threading;
using System.Runtime.InteropServices;

namespace TrayApp
{
    static class Program
    {
        private static NotifyIcon trayIcon;
        private static double glucoseValue = 5.0; // Default value
        private static HttpClient httpClient;
        private static System.Windows.Forms.Timer updateTimer;
        private static SynchronizationContext uiContext;
        private static bool isInRedZone = false;
        private static DateTime? lastSuccessfulLoadTime = null; // Track when data was last successfully loaded
        
        private const string ApiEndpoint = "https://gluco-watch-default-rtdb.europe-west1.firebasedatabase.app/users/78347/latest.json";
        private const double LOW_THRESHOLD = 3.9;
        private const double HIGH_THRESHOLD = 10.0;
        private const bool SHOW_CONSOLE = true; // Set to false to disable console window
        private const double DATA_AGE_THRESHOLD_MINUTES = 15.0; // Data is considered stale if older than this
        private const double LAST_LOAD_THRESHOLD_MINUTES = 10.0; // Consider offline if no data loaded in this time

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool AllocConsole();

        [STAThread]
        static void Main()
        {
            // Allocate a console window to see Console.WriteLine output (if enabled)
            if (SHOW_CONSOLE)
            {
                AllocConsole();
            }
            
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // Capture UI thread context
            uiContext = SynchronizationContext.Current ?? new WindowsFormsSynchronizationContext();

            httpClient = new HttpClient();

            trayIcon = new NotifyIcon();
            trayIcon.Visible = true;
            trayIcon.Text = "Glucose Monitor";

            // Initial icon
            trayIcon.Icon = CreateGlucoseIcon(glucoseValue);

            // Context menu
            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("Exit", null, (s, e) => Application.Exit());
            trayIcon.ContextMenuStrip = menu;

            // Set up timer to fetch data every 1 minute
            updateTimer = new System.Windows.Forms.Timer();
            updateTimer.Interval = 3000; // 1 minute in milliseconds
            updateTimer.Tick += async (s, e) => await FetchGlucoseData();
            updateTimer.Start();

            // Fetch immediately on startup
            _ = Task.Run(async () => await FetchGlucoseData());

            Application.Run();
        }

        static bool IsOffline(bool isDataStale)
        {
            // Check if data is stale (older than 15 minutes)
            if (isDataStale)
                return true;
            
            // Check if no data were loaded in last 10 minutes
            if (lastSuccessfulLoadTime.HasValue)
            {
                TimeSpan timeSinceLastLoad = DateTime.UtcNow - lastSuccessfulLoadTime.Value;
                if (timeSinceLastLoad.TotalMinutes > LAST_LOAD_THRESHOLD_MINUTES)
                {
                    return true;
                }
            }
            else
            {
                // No data ever loaded, consider offline
                return true;
            }
            
            return false;
        }

        static async Task FetchGlucoseData()
        {
            try
            {
                HttpResponseMessage response = await httpClient.GetAsync(ApiEndpoint);
                response.EnsureSuccessStatusCode();

                string jsonContent = await response.Content.ReadAsStringAsync();
                
                // Log the payload
                if (SHOW_CONSOLE)
                {
                    Console.WriteLine($"Received payload: {jsonContent}");
                }
                
                var jsonDoc = JsonDocument.Parse(jsonContent);

                // Navigate to main.glucose (Firebase Realtime DB structure)
                if (jsonDoc.RootElement.TryGetProperty("main", out var main) &&
                    main.TryGetProperty("glucose", out var glucose))
                {
                    double glucoseDouble = glucose.GetDouble();
                    
                    // Log main.timestamp and calculate data age
                    bool isDataStale = false;
                    if (main.TryGetProperty("timestamp", out var timestamp))
                    {
                        double timestampValue = timestamp.GetDouble();
                        
                        if (SHOW_CONSOLE)
                        {
                            Console.WriteLine($"main.timestamp: {timestamp.GetRawText()}");
                        }
                        
                        // Convert Unix timestamp to DateTime (Unix timestamps are always in UTC)
                        DateTimeOffset dataTime = DateTimeOffset.FromUnixTimeSeconds((long)timestampValue);
                        DateTime currentTime = DateTime.UtcNow; // Use UTC to match Unix timestamp
                        TimeSpan age = currentTime - dataTime.DateTime;
                        
                        // Check if data is stale (older than threshold)
                        isDataStale = age.TotalMinutes > DATA_AGE_THRESHOLD_MINUTES;
                        
                        if (SHOW_CONSOLE)
                        {
                            Console.WriteLine($"Data age: {age.TotalSeconds:F1} seconds ({age.TotalMinutes:F2} minutes)");
                            if (isDataStale)
                            {
                                Console.WriteLine($"Data is stale (older than {DATA_AGE_THRESHOLD_MINUTES} minutes)");
                            }
                        }
                    }

                    // Update last successful load time
                    lastSuccessfulLoadTime = DateTime.UtcNow;

                    // Update icon on UI thread
                    if (trayIcon != null && uiContext != null)
                    {
                        uiContext.Post(_ =>
                        {
                            bool wasInRedZone = isInRedZone;
                            bool nowInRedZone = glucoseDouble < LOW_THRESHOLD;
                            
                            // Check if we're offline (data stale OR no load in last 10 minutes)
                            bool isOffline = IsOffline(isDataStale);
                            
                            glucoseValue = glucoseDouble;
                            trayIcon.Icon?.Dispose();
                            trayIcon.Icon = CreateGlucoseIcon(glucoseValue, isOffline);
                            trayIcon.Text = isOffline ? $"Glucose: {glucoseValue:F1} (Offline)" : $"Glucose: {glucoseValue:F1}";
                            
                            // Handle red zone warnings - only show when first entering red zone
                            if (nowInRedZone)
                            {
                                // Just entered red zone - show warning only on first entry
                                if (!wasInRedZone)
                                {
                                    isInRedZone = true;
                                    ShowRedZoneWarning(glucoseDouble);
                                }
                                // If already in red zone, don't show notification again
                            }
                            else
                            {
                                // Left red zone - reset tracking
                                if (wasInRedZone)
                                {
                                    isInRedZone = false;
                                }
                            }
                        }, null);
                    }
                }
            }
            catch (Exception ex)
            {
                // On error, keep showing the last known value
                // Could optionally show an error icon or log the error
                System.Diagnostics.Debug.WriteLine($"Error fetching glucose data: {ex.Message}");
                
                // Check if we should show offline icon (no data loaded in last 10 minutes)
                if (trayIcon != null && uiContext != null)
                {
                    uiContext.Post(_ =>
                    {
                        // Check offline status (data is stale = false since we failed to load, but check time since last load)
                        bool isOffline = IsOffline(false);
                        
                        if (isOffline)
                        {
                            trayIcon.Icon?.Dispose();
                            trayIcon.Icon = CreateGlucoseIcon(glucoseValue, true);
                            trayIcon.Text = $"Glucose: {glucoseValue:F1} (Offline)";
                        }
                    }, null);
                }
            }
        }

        static Icon CreateGlucoseIcon(double value, bool isOffline = false)
        {
            Color bgColor = GetGlucoseColor(value, isOffline);

            Bitmap bmp = new Bitmap(16, 16);
            Graphics g = null;
            try
            {
                g = Graphics.FromImage(bmp);
                g.Clear(bgColor);
                g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

                // Round to nearest integer for display in small icon
                string text = Math.Round(value).ToString();

                // Try Segoe UI first, fallback to system font if not available
                Font font = null;
                try
                {
                    font = new Font("Segoe UI", 8, FontStyle.Bold, GraphicsUnit.Pixel);
                }
                catch
                {
                    font = new Font(SystemFonts.DefaultFont.FontFamily, 7, FontStyle.Bold, GraphicsUnit.Pixel);
                }

                try
                {
                    using (SolidBrush textBrush = new SolidBrush(Color.White))
                    {
                        SizeF size = g.MeasureString(text, font);

                        float x = Math.Max(0, (16 - size.Width) / 2);
                        float y = Math.Max(0, (16 - size.Height) / 2 - 1);

                        // Ensure coordinates are valid
                        if (!float.IsNaN(x) && !float.IsNaN(y) && !float.IsInfinity(x) && !float.IsInfinity(y))
                        {
                            g.DrawString(text, font, textBrush, x, y);
                        }
                    }
                }
                finally
                {
                    font?.Dispose();
                }
            }
            finally
            {
                g?.Dispose();
            }

            IntPtr hIcon = bmp.GetHicon();
            Icon icon = Icon.FromHandle(hIcon);
            // Create a copy so we can dispose the bitmap
            Icon result = new Icon(icon, icon.Size);
            icon.Dispose();
            bmp.Dispose();
            return result;
        }

        static void ShowRedZoneWarning(double value)
        {
            if (trayIcon != null)
            {
                trayIcon.BalloonTipTitle = "Glucose Warning";
                trayIcon.BalloonTipText = $"Your glucose is now at {value:F1} level";
                trayIcon.BalloonTipIcon = ToolTipIcon.Warning;
                trayIcon.ShowBalloonTip(5000); // Show for 5 seconds
            }
        }

        static Color GetGlucoseColor(double value, bool isOffline = false)
        {
            // If offline, show gray regardless of glucose value
            if (isOffline)
                return Color.Gray;
            
            if (value < LOW_THRESHOLD)
                return Color.Red;        // Low
            if (value > HIGH_THRESHOLD)
                return Color.Orange;     // High
            return Color.Green;          // Normal (LOW_THRESHOLD to HIGH_THRESHOLD)
        }
    }
}

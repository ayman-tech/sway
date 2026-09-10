import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Sway",
    short_name: "Sway",
    description: "Tasks, calendar, reminders, and Google Calendar import in one focused app.",
    start_url: "/dashboard/tasks",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#12161d",
    theme_color: "#2b6cff",
    categories: ["productivity", "utilities"],
    icons: [
      { src: "/icons/sway-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/sway-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/sway-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      {
        name: "Tasks",
        short_name: "Tasks",
        url: "/dashboard/tasks",
        icons: [{ src: "/icons/sway-192.png", sizes: "192x192" }],
      },
      {
        name: "Calendar",
        short_name: "Calendar",
        url: "/dashboard/calendar",
        icons: [{ src: "/icons/sway-192.png", sizes: "192x192" }],
      },
      {
        name: "Availability",
        short_name: "Availability",
        url: "/dashboard/availability",
        icons: [{ src: "/icons/sway-192.png", sizes: "192x192" }],
      },
    ],
  };
}

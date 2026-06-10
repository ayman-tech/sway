export type Task = {
  id: string;
  title: string;
  description: string | null;
  project_id: string | null;
  priority: number;
  status: "pending" | "completed";
  due_at: string | null;
  due_date: string | null;
  start_at: string | null;
  end_at: string | null;
  end_date: string | null;
  reminder_minutes_before: number | null;
  recurrence_rule: string | null;
  recurrence_timezone: string | null;
  recurrence_parent_id: string | null;
  google_event_id: string | null;
  source: "sway" | "google";
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  is_preview: boolean;
};

export type TaskGroup = {
  label: string;
  overdue: boolean;
  tasks: Task[];
};

export type UserSettings = {
  first_name: string | null;
  last_name: string | null;
  theme: "light" | "dark" | "system";
  reminders_processed_through: string | null;
  browser_notifications_enabled: boolean;
};

export type GoogleStatus = {
  configured: boolean;
  connected: boolean;
  setup_available: boolean;
  client_id: string | null;
  redirect_uri: string;
  account: string | null;
  last_synced_at: string | null;
  last_sync_error: string | null;
};

export type GoogleSyncResult = {
  imported: number;
  skipped: boolean;
};

export type AvailabilitySlots = Record<string, number[]>;

export type AvailabilitySnapshot = {
  selected_dates: string[];
  start_hour: number;
  end_hour: number;
  available_slots: AvailabilitySlots;
  busy_slots: AvailabilitySlots;
};

export type AvailabilityShareCreated = {
  url: string;
  expires_at: string;
};

export type AvailabilityShare = {
  snapshot: AvailabilitySnapshot;
  first_name: string | null;
  creator_timezone: string;
  created_at: string;
  expires_at: string;
};

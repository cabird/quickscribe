// Global custom event declarations 
import { Recording } from "../interfaces/Models";

interface RecordingUpdatedEventDetail {
  recording: Recording;
}

interface RecordingUpdatedEvent extends CustomEvent {
  detail: RecordingUpdatedEventDetail;
}

declare global {
  interface WindowEventMap {
    'recordingUpdated': RecordingUpdatedEvent;
  }
}

import { RotateCcw } from "lucide-react";
import { Button } from "../components/Button";

export default function Review({ go, photo }) {
  return (
    <div className="yw-enter mx-auto flex max-w-md flex-col items-center px-5 py-10 text-center">
      <div className="aspect-[3/4] w-full overflow-hidden rounded-[2rem] bg-mist">
        {photo && <img src={photo} alt="Your captured photo" className="h-full w-full object-cover" />}
      </div>
      <h2 className="mt-7 text-3xl text-jade">Happy with this photo?</h2>
      <p className="mt-2 text-sm text-ink-soft">Face fully visible, evenly lit, no shadows.</p>
      <div className="mt-7 flex w-full gap-3">
        <Button variant="ghost" icon={null} iconLeft={RotateCcw} full onClick={() => go("camera")}>Retake</Button>
        <Button full onClick={() => go("processing")} disabled={!photo}>Analyze</Button>
      </div>
    </div>
  );
}

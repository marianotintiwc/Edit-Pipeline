import type { WizardStep } from "../types";

interface WizardStepperProps {
  steps: WizardStep[];
  currentStepId: string;
}

export function WizardStepper({ steps, currentStepId }: WizardStepperProps) {
  return (
    <ol aria-label="Wizard steps">
      {steps.map((step, index) => (
        <li key={step.id} aria-current={step.id === currentStepId ? "step" : undefined}>
          Step {index + 1}: {step.title}
        </li>
      ))}
    </ol>
  );
}

// Shared by task estimates and focus blocks; selections stay independent.
export const DURATION_PRESETS = [5, 10, 15, 30, 45, 60];

export function createDurationPicker(container, { value = 15, onChange }) {
  const buttons = DURATION_PRESETS.map(minutes => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${minutes} min`;
    button.dataset.minutes = minutes;
    button.addEventListener('click', () => { setValue(minutes); onChange(minutes); });
    return button;
  });
  function setValue(next) {
    value = next;
    buttons.forEach(button => {
      const selected = Number(button.dataset.minutes) === value;
      button.classList.toggle('selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }
  container.replaceChildren(...buttons);
  setValue(value);
  return { setValue };
}

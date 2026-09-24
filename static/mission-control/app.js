// Progressive disclosure only; validation and record creation stay on the server.
document.querySelectorAll('[data-option-group]').forEach(group => {
  const name = group.dataset.optionGroup;
  const controls = document.querySelectorAll(`input[name="${name}"]`);
  const update = () => {
    const selected = Array.from(controls).find(input => input.checked);
    const visible = selected && selected.value === group.dataset.optionValue;
    group.hidden = !visible;
    group.querySelectorAll('input, select, textarea').forEach(input => { input.disabled = !visible; });
  };
  controls.forEach(input => input.addEventListener('change', update));
  update();
});
const skipService = document.getElementById('id_skip_service');
if (skipService) {
  const group = document.getElementById('service-fields');
  const update = () => {
    group.hidden = skipService.checked;
    group.querySelectorAll('input,select').forEach(input => { input.disabled = skipService.checked; });
  };
  skipService.addEventListener('change', update);
  update();
}
document.querySelectorAll('form[data-create-platform]').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = 'Creating Platform…';
  });
});

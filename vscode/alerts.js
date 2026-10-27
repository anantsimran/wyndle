'use strict';

class Alerts {
  constructor(show, enabled = {}) {
    this.show = show;
    this.enabled = enabled;
    this.seen = new Set();
    this.previous = undefined;
    this.identities = {};
  }
  deliver(event) {
    if (!event || typeof event.id !== 'string' || typeof event.title !== 'string'
      || typeof event.body !== 'string' || event.title.length > 200 || event.body.length > 2000
      || this.seen.has(event.id)) return;
    this.seen.add(event.id);
    if (this.seen.size > 1000) this.seen.delete(this.seen.values().next().value);
    this.show(`Wyndle · ${event.title}: ${event.body}`);
  }
  update(data) {
    const now = data.now;
    const latest = {};
    const identities = { timer: `${data.date}:${data.timer.kind}:${data.timer.end}`, daily: data.dailyAlarm?.id };
    for (const event of data.reminders || []) {
      if (this.enabled[event.channel] && this.identities[event.channel] === identities[event.channel]
        && this.previous < event.at && event.at <= now
        && (!latest[event.channel] || latest[event.channel].at < event.at)) latest[event.channel] = event;
    }
    for (const event of Object.values(latest)) this.deliver(event);
    this.previous = now;
    this.identities = identities;
  }
}
module.exports = { Alerts };

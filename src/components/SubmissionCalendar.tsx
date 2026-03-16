import { VenueView } from '../data/conferences';

interface SubmissionCalendarProps {
  venues: VenueView[];
  now: Date;
  favoriteVenueIds: string[];
}

interface MonthBucket {
  key: string;
  label: string;
  venues: VenueView[];
}

function getAoeMonthStart(now: Date) {
  const aoeNow = new Date(now.getTime() - 12 * 60 * 60 * 1000);
  return {
    year: aoeNow.getUTCFullYear(),
    month: aoeNow.getUTCMonth(),
  };
}

function getMonthKey(year: number, month: number) {
  return `${year}-${String(month + 1).padStart(2, '0')}`;
}

function getMonthLabel(year: number, month: number) {
  return new Date(Date.UTC(year, month, 1)).toLocaleString('en-US', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

function getDeadlineMonthKey(venue: VenueView) {
  const [datePart] = venue.countdownDeadline!.split('T');
  const [year, month] = datePart.split('-').map(Number);
  return getMonthKey(year, month - 1);
}

function getDeadlineDay(venue: VenueView) {
  const [datePart] = venue.countdownDeadline!.split('T');
  const [, , day] = datePart.split('-').map(Number);
  return day;
}

function SubmissionCalendar({ venues, now, favoriteVenueIds }: SubmissionCalendarProps) {
  const conferenceVenues = venues.filter((venue) => {
    return (
      venue.venueType === 'conference' &&
      venue.submissionModel === 'deadline' &&
      venue.countdownDeadline
    );
  });

  const start = getAoeMonthStart(now);
  const months: MonthBucket[] = Array.from({ length: 12 }, (_, index) => {
    const monthOffset = start.month + index;
    const year = start.year + Math.floor(monthOffset / 12);
    const month = monthOffset % 12;
    const key = getMonthKey(year, month);

    return {
      key,
      label: getMonthLabel(year, month),
      venues: conferenceVenues
        .filter((venue) => getDeadlineMonthKey(venue) === key)
        .sort((left, right) => (left.countdownDeadline! < right.countdownDeadline! ? -1 : 1)),
    };
  });

  return (
    <div className="calendar-grid">
      {months.map((month) => (
        <article key={month.key} className="calendar-month">
          <div className="calendar-month-head">
            <strong>{month.label}</strong>
          </div>
          {month.venues.length > 0 ? (
            <div className="calendar-list">
              {month.venues.map((venue) => (
                <div
                  key={venue.id}
                  className={
                    favoriteVenueIds.includes(venue.id)
                      ? 'calendar-item calendar-item-following'
                      : 'calendar-item'
                  }
                >
                  <span>{venue.title}</span>
                  <span>
                    {venue.countdownLabel === 'Abstract deadline' ? 'Abs.' : 'Paper'} {getDeadlineDay(venue)}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

export default SubmissionCalendar;

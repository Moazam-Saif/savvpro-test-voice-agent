"use client";

import React, { useEffect, useState } from "react";
import { DemoBooking, fetchDemoBookings } from "../lib/api";

export function DemoBookings() {
  const [bookings, setBookings] = useState<DemoBooking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDemoBookings().then((data) => {
      setBookings(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="card demo-card muted">Loading demo bookings...</div>;
  }

  if (bookings.length === 0) {
    return null;
  }

  return (
    <div className="card demo-card">
      <div className="demo-header">
        <h4>Demo Appointments for Testing</h4>
      </div>
      <p className="demo-desc">
        Use these pre-seeded patient names or 4-digit codes when testing appointment cancellation or verification:
      </p>
      <div className="demo-table-wrapper">
        <table className="demo-table">
          <thead>
            <tr>
              <th>Patient Name</th>
              <th>Service</th>
              <th>Date & Time</th>
              <th>Confirmation Code</th>
            </tr>
          </thead>
          <tbody>
            {bookings.slice(0, 5).map((b) => (
              <tr key={b.id}>
                <td><b>{b.patient_name}</b></td>
                <td>{b.service}</td>
                <td>{new Date(b.start).toLocaleString()}</td>
                <td><code className="code-pill">{b.code}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

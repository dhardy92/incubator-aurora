package com.twitter.mesos.scheduler.events;

import java.lang.annotation.Retention;
import java.lang.annotation.Target;
import java.util.Set;

import com.google.common.base.Objects;

import com.twitter.mesos.gen.ScheduleStatus;
import com.twitter.mesos.scheduler.SchedulingFilter.Veto;

import static java.lang.annotation.ElementType.METHOD;
import static java.lang.annotation.RetentionPolicy.RUNTIME;

import static com.google.common.base.Preconditions.checkNotNull;

/**
 * Event notifications related to tasks.
 */
public interface PubsubEvent {

  /**
   * Interface with no functionality, but identifies a class as supporting task pubsub events.
   */
  public interface EventSubscriber {
  }

  /**
   * Event sent when tasks were deleted.
   */
  public static class TasksDeleted implements PubsubEvent {
    private final Set<String> taskIds;

    public TasksDeleted(Set<String> taskIds) {
      this.taskIds = checkNotNull(taskIds);
    }

    public Set<String> getTaskIds() {
      return taskIds;
    }

    @Override
    public boolean equals(Object o) {
      if (!(o instanceof TasksDeleted)) {
        return false;
      }

      TasksDeleted other = (TasksDeleted) o;
      return Objects.equal(taskIds, other.taskIds);
    }

    @Override
    public int hashCode() {
      return Objects.hashCode(taskIds);
    }
  }

  /**
   * Event sent when a task changed state.
   */
  public static class TaskStateChange implements PubsubEvent {
    private final String taskId;
    private final ScheduleStatus oldState;
    private final ScheduleStatus newState;

    public TaskStateChange(String taskId, ScheduleStatus oldState, ScheduleStatus newState) {
      this.taskId = checkNotNull(taskId);
      this.oldState = checkNotNull(oldState);
      this.newState = checkNotNull(newState);
    }

    public String getTaskId() {
      return taskId;
    }

    public ScheduleStatus getOldState() {
      return oldState;
    }

    public ScheduleStatus getNewState() {
      return newState;
    }

    @Override
    public boolean equals(Object o) {
      if (!(o instanceof TaskStateChange)) {
        return false;
      }

      TaskStateChange other = (TaskStateChange) o;
      return Objects.equal(taskId, other.taskId)
          && Objects.equal(oldState, other.oldState)
          && Objects.equal(newState, other.newState);
    }

    @Override
    public int hashCode() {
      return Objects.hashCode(taskId, oldState, newState);
    }
  }

  /**
   * Event sent when a scheduling assignment was vetoed.
   */
  public static class Vetoed implements PubsubEvent {
    private final String taskId;
    private final Set<Veto> vetoes;

    public Vetoed(String taskId, Set<Veto> vetoes) {
      this.taskId = checkNotNull(taskId);
      this.vetoes = checkNotNull(vetoes);
    }

    public String getTaskId() {
      return taskId;
    }

    public Set<Veto> getVetoes() {
      return vetoes;
    }

    @Override
    public boolean equals(Object o) {
      if (!(o instanceof Vetoed)) {
        return false;
      }

      Vetoed other = (Vetoed) o;
      return Objects.equal(taskId, other.taskId)
          && Objects.equal(vetoes, other.vetoes);
    }

    @Override
    public int hashCode() {
      return Objects.hashCode(taskId, vetoes);
    }
  }

  public static class TaskRescheduled implements PubsubEvent {
    private final String role;
    private final String job;
    private final int shard;

    public TaskRescheduled(String role, String job, int shard) {
      this.role = role;
      this.job = job;
      this.shard = shard;
    }

    public String getRole() {
      return role;
    }

    public String getJob() {
      return job;
    }

    public int getShard() {
      return shard;
    }

    @Override
    public boolean equals(Object o) {
      if (!(o instanceof TaskRescheduled)) {
        return false;
      }

      TaskRescheduled other = (TaskRescheduled) o;
      return Objects.equal(role, other.role)
          && Objects.equal(job, other.job)
          && Objects.equal(shard, other.shard);
    }

    @Override
    public int hashCode() {
      return Objects.hashCode(role, job, shard);
    }
  }

  public static class StorageStarted implements PubsubEvent {
    @Override
    public boolean equals(Object o) {
      return (o != null) && getClass().equals(o.getClass());
    }

    @Override
    public int hashCode() {
      return getClass().hashCode();
    }
  }

  public static class DriverRegistered implements PubsubEvent {
    @Override
    public boolean equals(Object o) {
      return (o != null) && getClass().equals(o.getClass());
    }

    @Override
    public int hashCode() {
      return getClass().hashCode();
    }
  }

  public static final class Interceptors {
    private Interceptors() {
      // Utility class.
    }

    public enum Event {
      None(null),
      StorageStarted(new StorageStarted()),
      DriverRegistered(new DriverRegistered());

      final PubsubEvent event;
      private Event(PubsubEvent event) {
        this.event = event;
      }
    }

    /**
     * An annotation to place on methods of injected classes that which to fire events before
     * and/or after their invocation.
     */
    @Target(METHOD) @Retention(RUNTIME)
    public @interface Notify {
      /**
       * Event to fire prior to invocation.
       */
      Event before() default Event.None;

      /**
       * Event to fire after invocation.
       */
      Event after() default Event.None;
    }
  }
}
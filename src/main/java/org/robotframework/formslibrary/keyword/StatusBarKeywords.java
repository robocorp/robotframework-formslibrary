package org.robotframework.formslibrary.keyword;

import java.util.ArrayList;
import java.util.List;

import org.robotframework.formslibrary.operator.StatusBarOperator;
import org.robotframework.javalib.annotation.ArgumentNames;
import org.robotframework.javalib.annotation.RobotKeyword;
import org.robotframework.javalib.annotation.RobotKeywords;

@RobotKeywords
public class StatusBarKeywords {

    @RobotKeyword("Get the message that is displayed in the default status bar"
      + " at the bottom of the screen. \n\n "
      + "Example:\n "
      + "| Get Status Message |\n")
    public String getStatusMessage() {
        return new StatusBarOperator().getMessage();
    }

    @RobotKeyword("Get all the messages that are displayed in all the status bars"
      + " at the bottom of the screen. Choose which status bars are used by index.\n\n "
      + "Example:\n "
      + "| Get All Status Messages | 0 | 1\n")
    @ArgumentNames({ "*statusBarIndexes" })
    public List<List <String>> getAllStatusMessages(String... statusBarIndexes) {
        // Robot Framework convert arguments to strings, so don't use ints here
        List<List <String>> allMessages = new ArrayList<>();
        for (String index: statusBarIndexes) {
          int i = Integer.parseInt(index);
          List <String> messages = new StatusBarOperator(i).getAllMessages();
          allMessages.add(messages);
        }
        return allMessages;
    }

    @RobotKeyword("Verify that the status bar at the bottom of the screen contains certain content.\n\n" + "Example:\n"
            + "| Verify Status Message | _No Record Found_ | \n")
    @ArgumentNames({ "value" })
    public void verifyStatusMessage(String value) {
        new StatusBarOperator().verifyValue(value);
    }
}

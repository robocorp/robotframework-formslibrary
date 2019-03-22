package org.robotframework.formslibrary.operator;

import java.util.ArrayList;
import java.util.List;

import org.robotframework.formslibrary.FormsLibraryException;
import org.robotframework.formslibrary.chooser.ByComponentTypeChooser;
import org.robotframework.formslibrary.util.ComponentType;
import org.robotframework.formslibrary.util.Logger;
import org.robotframework.formslibrary.util.ObjectUtil;
import org.robotframework.formslibrary.util.TextUtil;

/**
 * Oracle Forms Status Bar operator.
 */
public class StatusBarOperator extends AbstractRootComponentOperator {
    /**
     * Create a new operator for the default status bar.
     */
    public StatusBarOperator() {
        super(new ByComponentTypeChooser(0, ComponentType.STATUS_BAR));
    }

    /**
     * Create a new operator for the chosen status bar.
     * Status bar is chosen by index, if the form contains
     * multiple status bars.
     */
    public StatusBarOperator(int statusBarIndex) {
      // TODO: make this work with statusBarIndex = -1
      // which should return *all* status bars here
        super(new ByComponentTypeChooser(statusBarIndex, ComponentType.STATUS_BAR));
    }

    /**
     * @return the main message displayed in the status bar.
     */
    public String getMessage() {
        Object[] statusBarItems = (Object[]) ObjectUtil.invokeMethod(getSource(), "getItems()");
        String result = "";
        for (int i = 0; i < statusBarItems.length; i++) {
            if (ComponentType.STATUS_BAR_TEXT_ITEM.matches(statusBarItems[i])) {
                result = ObjectUtil.getString(statusBarItems[i], "getText()");
                Logger.info("Found status message '" + result + "'");
                break;
            }
        }
        return result;
    }

    /**
     * @return the all the messages displayed in the status bar.
     */
    public List<String> getAllMessages() {

        Object[] statusBarItems = (Object[]) ObjectUtil.invokeMethod(getSource(), "getItems()");
        List<String> results = new ArrayList<>();
        String result = "";

        for (int i = 0; i < statusBarItems.length; i++) {
            if (ComponentType.STATUS_BAR_TEXT_ITEM.matches(statusBarItems[i])) {
                result = ObjectUtil.getString(statusBarItems[i], "getText()");
                Logger.info("Found status message '" + result + "'");
                results.add(result);
            }
        }
        return results;
    }

    /**
     * Verify that the given value is displayed in the status bar.
     */
    public void verifyValue(String value) {
        String message = getMessage();
        if (!TextUtil.matches(message, value)) {
            throw new FormsLibraryException("Status Bar Message '" + message + "' does not match '" + value + "'.");
        }
    }

}
